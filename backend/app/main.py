import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.chats.router import router as chats_router
from app.config import Settings
from app.db import init_db
from app.llm import LLM, StubLLM, build_llm
from app.spa import mount_spa
from app.tools import ToolRegistry, build_registry

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger(__name__)


def create_app(
    settings: Settings | None = None, llm: LLM | None = None, tools: ToolRegistry | None = None
) -> FastAPI:
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        engine = create_async_engine(settings.database_url)
        await init_db(engine)
        app.state.sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
        app.state.llm = llm or build_llm(settings)
        app.state.tools = tools if tools is not None else build_registry()
        if isinstance(app.state.llm, StubLLM):
            log.warning("LLM_API_KEY or LLM_MODEL is not set, chat replies come from the stub")
        yield
        await engine.dispose()

    app = FastAPI(title="1surak API", version="0.1.0", lifespan=lifespan)

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok"}

    app.include_router(chats_router)
    mount_spa(app, Path(settings.static_dir))
    return app


app = create_app()
