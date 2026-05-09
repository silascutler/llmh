from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = Field(alias="DATABASE_URL")
    database_disable_pool: bool = Field(default=False, alias="DATABASE_DISABLE_POOL")
    redis_url: str = Field(alias="REDIS_URL")
    redis_ingest_stream: str = Field(alias="REDIS_INGEST_STREAM")
    redis_consumer_group: str = Field(alias="REDIS_CONSUMER_GROUP")
    meili_url: str = Field(alias="MEILI_URL")
    meili_master_key: str = Field(alias="MEILI_MASTER_KEY")
    ingest_bearer_token: str = Field(alias="INGEST_BEARER_TOKEN")
    session_secret: str = Field(alias="SESSION_SECRET")
    cors_origins: str = Field(default="http://localhost:3000", alias="CORS_ORIGINS")
    cors_origin_regex: str | None = Field(default=None, alias="CORS_ORIGIN_REGEX")
    session_https_only: bool = Field(default=True, alias="SESSION_HTTPS_ONLY")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    raw_payload_max_bytes: int = Field(default=65536, alias="RAW_PAYLOAD_MAX_BYTES")
    ingest_batch_max: int = Field(default=500, alias="INGEST_BATCH_MAX")
    ingest_rate_limit_per_minute: int = Field(default=1200, alias="INGEST_RATE_LIMIT_PER_MINUTE")
    smtp_host: str | None = Field(default=None, alias="SMTP_HOST")
    smtp_port: int = Field(default=587, alias="SMTP_PORT")
    smtp_user: str | None = Field(default=None, alias="SMTP_USER")
    smtp_password: str | None = Field(default=None, alias="SMTP_PASSWORD")
    smtp_from: str = Field(default="llmh@localhost", alias="SMTP_FROM")
    smtp_starttls: bool = Field(default=True, alias="SMTP_STARTTLS")
    next_public_api_base_url: str = Field(default="http://localhost:8000", alias="NEXT_PUBLIC_API_BASE_URL")

    @property
    def cors_origins_list(self) -> list[str]:
        value = self.cors_origins
        if not value:
            return []
        if value.startswith("["):
            import json

            return json.loads(value)
        return [item.strip() for item in value.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
