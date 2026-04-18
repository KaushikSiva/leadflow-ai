from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import model_validator


def _normalize_database_url(database_url: str) -> str:
    value = (database_url or "").strip()
    if value.startswith("postgres://"):
        value = "postgresql+psycopg://" + value[len("postgres://") :]
    elif value.startswith("postgresql://") and not value.startswith("postgresql+"):
        value = "postgresql+psycopg://" + value[len("postgresql://") :]

    if "supabase.co" in value and "sslmode=" not in value:
        separator = "&" if "?" in value else "?"
        value = f"{value}{separator}sslmode=require"

    return value


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    env: str = Field(default="development", alias="ENV")
    app_name: str = Field(default="LeadFlow AI", alias="APP_NAME")
    app_base_url: str = Field(default="http://localhost:8080", alias="APP_BASE_URL")

    database_url: str = Field(alias="DATABASE_URL")

    openai_api_key: str = Field(alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4o-mini", alias="OPENAI_MODEL")

    apify_api_token: str = Field(alias="APIFY_API_TOKEN")
    apify_profile_actor_id: str = Field(alias="APIFY_PROFILE_ACTOR_ID")
    apify_phone_enrich_actor_id: str = Field(alias="APIFY_PHONE_ENRICH_ACTOR_ID")
    apify_timeout_seconds: int = Field(default=120, alias="APIFY_TIMEOUT_SECONDS")

    voicecall_api_base_url: str = Field(alias="VOICECALL_API_BASE_URL")
    voicecall_api_token: str = Field(alias="VOICECALL_API_TOKEN")
    voicecall_from_number: str | None = Field(default=None, alias="VOICECALL_FROM_NUMBER")
    voicecall_destination_number: str = Field(default="+12149098059", alias="VOICECALL_DESTINATION_NUMBER")

    worker_poll_seconds: int = Field(default=5, alias="WORKER_POLL_SECONDS")
    worker_batch_size: int = Field(default=1, alias="WORKER_BATCH_SIZE")

    @model_validator(mode="after")
    def normalize_urls(self) -> "Settings":
        self.database_url = _normalize_database_url(self.database_url)
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
