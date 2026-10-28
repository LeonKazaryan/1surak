import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import timedelta
from pathlib import Path

from fastapi import FastAPI
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.catalog.catalog import load_catalog
from app.catalog.seed import load_catalog_facts
from app.chats.router import router as chats_router
from app.config import Settings
from app.db import init_db
from app.destinations import reachable
from app.destinations.climate import ClimateFetcher
from app.destinations.live import LiveDirections
from app.flights import NoFlights, TravelpayoutsFlights, network
from app.flights.fares import FareStore
from app.flights.router import router as places_router
from app.fx import Rates
from app.fx import configure as configure_rates
from app.ground import GroundTransport
from app.ground import configure as configure_ground
from app.ground.flixbus import FlixBuses
from app.ground.tutu import TutuTrains
from app.ground.yandex import YandexRasp
from app.hotels import EstimatedOffers, HotelSource
from app.hotels.cache import CachedOffers, OfferStore
from app.hotels.evidence import EvidenceFinder, WishJudge
from app.hotels.liteapi import LiteApi, LiteOffers
from app.hotels.live import LiveStays
from app.hotels.osm import OsmHotels
from app.kb.embeddings import Embedder, FastEmbedder
from app.kb.page import page_tools_for
from app.kb.seed import backfill_embeddings, load_kb_seed
from app.kb.web import OpenAIWebSearch, web_search_for
from app.llm import LLM, OpenAICompatibleLLM, StubLLM, build_llm
from app.lookups import LookupStore
from app.plan.live_guide import LiveGuides, SeedGuides
from app.plan.live_guide import configure as configure_guides
from app.plan.taxi import NoTaxiFares, TaxiFares
from app.plan.taxi import configure as configure_taxi
from app.ratelimit import RateLimit
from app.spa import mount_spa
from app.tools import ToolRegistry, build_registry
from app.visas import NoFees, VisaFees
from app.visas import configure as configure_fees
from app.visas.router import router as visa_router
from app.visas.rules import current_passport

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger(__name__)


async def _load_seed(sessionmaker) -> None:
    # A broken seed must not take the whole app down: chat still works, the agent just knows less.
    try:
        await load_catalog_facts(sessionmaker)
    except Exception:
        log.exception("Could not load the destination catalogue seed")
    try:
        await load_kb_seed(sessionmaker)
    except Exception:
        log.exception("Could not load the knowledge base seed")


async def _embed_missing(sessionmaker, embedder: Embedder | None) -> None:
    # The first start embeds the whole seed once; later starts only find what has no vector yet.
    try:
        await backfill_embeddings(sessionmaker, embedder)
    except Exception:
        log.exception("Could not embed the knowledge base, search runs on words only")


def create_app(
    settings: Settings | None = None,
    llm: LLM | None = None,
    tools: ToolRegistry | None = None,
    embedder: Embedder | None = None,
) -> FastAPI:
    settings = settings or Settings()
    embedder = embedder or (FastEmbedder() if settings.embeddings else None)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        engine = create_async_engine(settings.database_url)
        await init_db(engine)
        app.state.sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
        app.state.llm = llm or build_llm(settings)
        if settings.seed_catalog:
            await _load_seed(app.state.sessionmaker)
        await _embed_missing(app.state.sessionmaker, embedder)
        flights = (
            TravelpayoutsFlights(
                settings.travelpayouts_token,
                store=FareStore(app.state.sessionmaker),
                network=network(),
                per_minute=settings.travelpayouts_per_minute,
            )
            if settings.travelpayouts_token
            else NoFlights()
        )
        if isinstance(flights, NoFlights):
            log.warning("TRAVELPAYOUTS_TOKEN is not set, the agent has no flight prices")
        else:
            await flights.start()
        refresher = None
        if isinstance(flights, TravelpayoutsFlights) and settings.fare_refresh_minutes > 0:
            every = timedelta(minutes=settings.fare_refresh_minutes)
            refresher = asyncio.create_task(flights.keep_fresh(every, settings.fare_refresh_budget))
        app.state.flights = flights
        # hotel offers: estimated today, cached like fares so a real provider plugs in behind the same cache
        hotel_offers = CachedOffers(EstimatedOffers(), OfferStore(app.state.sessionmaker))
        web = web_search_for(settings, app.state.llm)
        pages = page_tools_for(settings, app.state.llm) if web is not None else None
        agent_llm = app.state.llm
        wishes = (
            EvidenceFinder(
                app.state.sessionmaker,
                WishJudge(agent_llm.client, settings.extract_model or agent_llm.model),
                search=web,
                reader=pages.reader,
            )
            if settings.hotel_wishes and pages and isinstance(agent_llm, OpenAICompatibleLLM)
            else None
        )
        # live rates, rooms and photos where LiteAPI has them; the estimates above everywhere else
        stays = None
        if settings.lite_api:
            lite = LiteApi(settings.lite_api, LookupStore(app.state.sessionmaker))
            live_offers = CachedOffers(LiteOffers(lite), OfferStore(app.state.sessionmaker))
            stays = LiveStays(lite, live_offers, current_passport)
            log.info("Hotels: live LiteAPI rates%s", " (sandbox)" if lite.sandbox else "")
        app.state.hotels = HotelSource(
            hotel_offers,
            live=OsmHotels(app.state.sessionmaker) if settings.osm_hotels else None,
            evidence=wishes,
            stays=stays,
        )
        hotel_refreshers = []
        if settings.fare_refresh_minutes > 0:
            every = timedelta(minutes=settings.fare_refresh_minutes)
            hotel_refreshers = [
                asyncio.create_task(offers.keep_fresh(every, settings.fare_refresh_budget))
                for offers in (hotel_offers, stays and stays.offers)
                if offers
            ]
        climate = ClimateFetcher(app.state.sessionmaker) if settings.destination_climate else None
        # where people fly from each city now, from Aviasales; the stale route map only fills the gaps
        token = settings.travelpayouts_token
        directions = LiveDirections(token) if token and settings.destination_climate else None
        if climate:
            # the cities people fly to from the usual departure cities: their climate loads in the background
            for origin in filter(None, settings.destination_prefetch.split(",")):
                await climate.ensure(reachable(network(), origin.strip()), urgent=False)
        # visa fees: found on the web once per passport and country, read by the model, cached for a month
        # what is found on the web once and kept: visa fees and the cities' airport taxi fares
        visa_fees, taxi_fares = NoFees(), NoTaxiFares()
        if isinstance(agent_llm, OpenAICompatibleLLM):
            reader = settings.extract_model or agent_llm.model
            # the app's search first; the model's own web search (Responses API) when it is rate-limited
            searches = [s for s in (web, OpenAIWebSearch(agent_llm.client, reader)) if s is not None]
            store = LookupStore(app.state.sessionmaker)
            visa_fees = VisaFees(store, searches, agent_llm.client, reader)
            taxi_fares = TaxiFares(store, searches, agent_llm.client, reader, load_catalog().find)
        configure_fees(visa_fees)
        configure_taxi(taxi_fares)
        city_guides = SeedGuides()
        if settings.live_guides:
            fast = agent_llm if isinstance(agent_llm, OpenAICompatibleLLM) else None
            city_guides = LiveGuides(
                LookupStore(app.state.sessionmaker),
                load_catalog().find,
                fast.client if fast else None,
                (settings.extract_model or fast.model) if fast else "",
                google_key=settings.google_places_api_key,
            )
        configure_guides(city_guides)
        if settings.live_rates:
            configure_rates(Rates())
        if settings.ground_transport:
            configure_ground(
                GroundTransport(
                    TutuTrains(),
                    FlixBuses() if settings.flixbus else None,
                    YandexRasp(settings.yandex_rasp_key) if settings.yandex_rasp_key else None,
                )
            )
        if tools is not None:
            app.state.tools = tools
        else:
            app.state.tools = build_registry(
                app.state.sessionmaker, web, pages, flights, embedder, climate, directions
            )
        if isinstance(app.state.llm, StubLLM):
            log.warning("LLM_API_KEY or LLM_MODEL is not set, chat replies come from the stub")
        yield
        for task in (refresher, *hotel_refreshers):
            if task:
                task.cancel()
        await hotel_offers.settle()
        if stays:
            await stays.settle()
        await visa_fees.settle()
        await taxi_fares.settle()
        await city_guides.settle()
        if climate:
            climate.stop()
        if isinstance(flights, TravelpayoutsFlights):
            await flights.settle()
        await engine.dispose()

    app = FastAPI(title="1surak API", version="0.1.0", lifespan=lifespan)
    app.state.rate_limit = RateLimit(settings.rate_limit_per_minute)

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok"}

    app.include_router(chats_router)
    app.include_router(places_router)
    app.include_router(visa_router)
    mount_spa(app, Path(settings.static_dir))
    return app


app = create_app()
