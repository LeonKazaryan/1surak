import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import timedelta
from pathlib import Path

from fastapi import FastAPI
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.catalog.seed import load_catalog_facts
from app.chats.router import router as chats_router
from app.config import Settings
from app.db import init_db
from app.flights import NoFlights, TravelpayoutsFlights, network
from app.flights.fares import FareStore
from app.flights.router import router as places_router
from app.ground import GroundTransport
from app.ground import configure as configure_ground
from app.ground.flixbus import FlixBuses
from app.ground.tutu import TutuTrains
from app.kb.embeddings import Embedder, FastEmbedder
from app.kb.page import page_tools_for
from app.kb.seed import backfill_embeddings, load_kb_seed
from app.kb.web import web_search_for
from app.llm import LLM, StubLLM, build_llm
from app.ratelimit import RateLimit
from app.spa import mount_spa
from app.tools import ToolRegistry, build_registry

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
        if settings.ground_transport:
            configure_ground(GroundTransport(TutuTrains(), FlixBuses() if settings.flixbus else None))
        if tools is not None:
            app.state.tools = tools
        else:
            web = web_search_for(settings, app.state.llm)
            pages = page_tools_for(settings, app.state.llm) if web is not None else None
            app.state.tools = build_registry(app.state.sessionmaker, web, pages, flights, embedder)
        if isinstance(app.state.llm, StubLLM):
            log.warning("LLM_API_KEY or LLM_MODEL is not set, chat replies come from the stub")
        yield
        if refresher:
            refresher.cancel()
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
    mount_spa(app, Path(settings.static_dir))
    return app


app = create_app()
