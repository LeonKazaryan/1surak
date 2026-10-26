from typing import Literal

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore", populate_by_name=True)

    database_url: str = "postgresql+asyncpg://onesurak:onesurak@127.0.0.1:5433/onesurak"
    static_dir: str = "static"
    seed_catalog: bool = True
    embeddings: bool = True  # search the knowledge base by meaning too, with a local model

    llm_base_url: str = ""
    # OPENAI_API_KEY is what most people already have set; LLM_API_KEY wins when both are there
    llm_api_key: str = Field("", validation_alias=AliasChoices("LLM_API_KEY", "OPENAI_API_KEY"))
    llm_model: str = ""
    # How long the model thinks before it answers; empty leaves the model's default. Used only on OpenAI.
    llm_reasoning_effort: Literal["", "none", "low", "medium", "high", "xhigh", "max"] = ""
    llm_timeout_s: float = 60.0
    rate_limit_per_minute: int = Field(20, ge=0)  # chat turns and refreshes per client a minute; 0 is off

    # Web search for the knowledge base: auto | brave | tavily | openai | none (see app/kb/web.py).
    # Brave needs a key; Tavily works without one (rate-limited).
    search_provider: str = "auto"
    brave_api_key: str = Field("", validation_alias=AliasChoices("BRAVE_API_KEY", "BRAVE_SEARCH_API_KEY"))
    tavily_api_key: str = ""
    search_timeout_s: float = 10.0

    # read_page: opens one web page and pulls out the facts that answer a question.
    jina_api_key: str = ""  # optional: Jina Reader works without a key at 20 pages a minute
    extract_model: str = ""  # the model that pulls facts out of a page; LLM_MODEL when empty
    page_timeout_s: float = 12.0

    # Real flight prices (Aviasales Data API). Without a token the agent has no flights and says so.
    travelpayouts_token: str = ""
    # Trains (Tutu.ru timetable through Travelpayouts) and buses (FlixBus) between the cities of a route.
    # Both are keyless; FlixBus is its website's undocumented API, so it has its own switch.
    ground_transport: bool = True
    flixbus: bool = True
    travelpayouts_per_minute: float = 300.0  # our guess at a polite rate; lower it if Aviasales answers 429
    # Popular fares are refreshed before they expire: how often to look, and how many requests per look.
    fare_refresh_minutes: float = 10.0  # 0 turns it off
    fare_refresh_budget: int = 60
