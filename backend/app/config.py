from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore", populate_by_name=True)

    database_url: str = "sqlite+aiosqlite:///./data/1surak.db"
    static_dir: str = "static"
    seed_catalog: bool = True

    llm_base_url: str = ""
    # OPENAI_API_KEY is what most people already have set; LLM_API_KEY wins when both are there
    llm_api_key: str = Field("", validation_alias=AliasChoices("LLM_API_KEY", "OPENAI_API_KEY"))
    llm_model: str = ""
    llm_timeout_s: float = 60.0

    # Web search for the knowledge base. Tavily works without a key (rate-limited); "none" turns it off.
    search_provider: str = "tavily"
    tavily_api_key: str = ""
    search_timeout_s: float = 10.0
