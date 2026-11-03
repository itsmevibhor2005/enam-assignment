"""Application configuration.

Every tunable lives here and is overridable by environment variable, so the
same image runs locally, in Docker and on a host without code changes.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # --- app ---------------------------------------------------------------
    app_name: str = "FINN"
    environment: str = Field(default="development")
    log_level: str = Field(default="INFO")
    cors_origins: str = Field(default="http://localhost:3000")

    # --- storage -----------------------------------------------------------
    database_url: str = Field(default="postgresql+psycopg://finn:finn@db:5432/finn")
    cache_dir: Path = Field(default=BASE_DIR / "data" / "cache")
    seed_dir: Path = Field(default=BASE_DIR / "data" / "seed")

    # --- data sourcing -----------------------------------------------------
    # "live"   : scrape only, fail loudly
    # "hybrid" : scrape, fall back to seeded fixtures per-source on failure
    # "seed"   : fixtures only, no outbound calls
    data_mode: str = Field(default="hybrid")
    http_timeout_seconds: float = Field(default=20.0)
    http_max_retries: int = Field(default=3)

    # --- LLM routing -------------------------------------------------------
    # Tier names are provider-agnostic; the concrete model is resolved in
    # app.llm.router from these settings.
    llm_provider: str = Field(default="anthropic")  # anthropic|openai|gemini|null
    llm_model_cheap: str = Field(default="claude-haiku-4-5")
    llm_model_strong: str = Field(default="claude-sonnet-4-6")
    llm_max_tokens: int = Field(default=2048)
    llm_cache_enabled: bool = Field(default=True)

    anthropic_api_key: str | None = None
    openai_api_key: str | None = None
    google_api_key: str | None = None
    groq_api_key: str | None = None

    # --- alerting defaults (user-overridable at runtime) -------------------
    default_volume_multiple: float = Field(default=2.0)
    default_price_move_pct: float = Field(default=4.0)
    default_digest_hours: int = Field(default=24)

    # --- scheduling --------------------------------------------------------
    scheduler_enabled: bool = Field(default=True)
    ingest_hour_ist: int = Field(default=19)  # after NSE close + filing settle

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def use_seed_fallback(self) -> bool:
        return self.data_mode in {"hybrid", "seed"}

    @property
    def allow_network(self) -> bool:
        return self.data_mode in {"hybrid", "live"}


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
