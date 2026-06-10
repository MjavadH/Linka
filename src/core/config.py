from functools import lru_cache
from typing import Literal

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-based application settings."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    environment: Literal["local", "development", "staging", "production"] = "local"
    bot_token: str = Field(..., min_length=10)
    bot_username: str = Field(..., min_length=1)
    archive_chat_id: int | None = None
    database_url: str = Field(..., min_length=1)
    redis_url: str | None = None
    admin_telegram_ids: tuple[int, ...] = ()
    file_delete_after_seconds: int = Field(
        default=3600,
        ge=1,
        validation_alias=AliasChoices("FILE_DELETE_AFTER_SECONDS", "DELETE_AFTER_SECONDS"),
    )
    scheduler_interval_seconds: int = Field(default=30, ge=5)
    sponsor_verification_interval_seconds: int = Field(default=300, ge=60)
    sponsor_verification_batch_size: int = Field(default=100, ge=1, le=1000)
    broadcast_rate_limit_per_second: int = Field(default=20, ge=1, le=30)
    broadcast_batch_size: int = Field(default=100, ge=1)
    premium_default_duration_days: int = Field(default=30, ge=1)
    log_level: str = "INFO"

    @field_validator("admin_telegram_ids", mode="before")
    @classmethod
    def parse_admin_ids(cls, value: object) -> tuple[int, ...]:
        if value in (None, ""):
            return ()
        if isinstance(value, str):
            return tuple(int(part.strip()) for part in value.split(",") if part.strip())
        if isinstance(value, (list, tuple, set)):
            return tuple(int(item) for item in value)
        raise TypeError("ADMIN_TELEGRAM_IDS must be a comma-separated string or sequence")

    @property
    def bot_deep_link_base(self) -> str:
        return f"https://t.me/{self.bot_username}?start="


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
