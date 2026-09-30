"""Runtime settings loaded from environment variables."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DBM_", env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./dbm.db"
    api_token: str | None = None
    api_url: str = "http://localhost:8000"
    coordinator_url: str = "http://localhost:8000"
    lease_ttl_seconds: int = Field(default=600, ge=30, le=86_400)


@lru_cache
def get_settings() -> Settings:
    return Settings()
