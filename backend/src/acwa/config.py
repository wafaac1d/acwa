"""Application settings.

Secrets are read from the environment and are never returned by the API.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEV_FERNET_KEY = "LT9kgrT3RvPvRfszF9yrxTTVqCqlwnkN7nlzgzwzjLo="
PROMPT_VERSION = "acwa-prompt-v1"
THREADS_TEXT_LIMIT = 500


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="ACWA_",
        env_file=(".env", "../.env"),
        extra="ignore",
    )

    database_url: str = Field(
        default="postgresql+psycopg://acwa:acwa@localhost:5432/acwa",
    )
    integration_mode: Literal["demo", "live"] = "demo"
    auth_token: str | None = None
    token_encryption_key: str = DEV_FERNET_KEY
    demo_seed: bool = True

    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_api_key: str | None = None
    deepseek_model: str = "deepseek-flash"
    deepseek_timeout_seconds: float = 60
    deepseek_max_retries: int = 2
    deepseek_temperature: float = 0.8
    deepseek_max_tokens: int = 512

    threads_graph_base_url: str = "https://graph.threads.com"
    threads_oauth_authorize_url: str = "https://threads.com/oauth/authorize"
    threads_app_id: str | None = None
    threads_app_secret: str | None = None
    threads_redirect_uri: str = "http://localhost:8000/api/accounts/threads/callback"
    threads_timeout_seconds: float = 30
    threads_scopes: str = "threads_basic,threads_content_publish,threads_manage_insights"
    threads_publish_quota_fallback: int = 250

    frontend_origin: str = "http://localhost:5173"
    cors_origins: str = "http://localhost:5173"
    worker_poll_seconds: float = 2
    worker_lease_seconds: int = 300
    missed_slot_grace_seconds: int = 15 * 60
    container_wait_seconds: int = 30
    max_publish_attempts: int = 5
    max_generate_attempts: int = 3
    recent_posts_in_prompt: int = 5
    log_level: str = "INFO"

    @field_validator("deepseek_model")
    @classmethod
    def supported_model(cls, value: str) -> str:
        allowed = {"deepseek-flash", "deepseek-v4-pro"}
        if value not in allowed:
            raise ValueError("ACWA_DEEPSEEK_MODEL must be deepseek-flash or deepseek-v4-pro")
        return value

    @field_validator("deepseek_temperature")
    @classmethod
    def temperature_range(cls, value: float) -> float:
        if not 0 <= value <= 2:
            raise ValueError("temperature must be between 0 and 2")
        return value

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    @property
    def threads_scope_list(self) -> list[str]:
        return [item.strip() for item in self.threads_scopes.split(",") if item.strip()]

    @property
    def live_key_is_dev_default(self) -> bool:
        return self.token_encryption_key == DEV_FERNET_KEY


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    password = settings.auth_token or ""
    if len(password) < 12:
        raise RuntimeError(
            "Set ACWA_AUTH_TOKEN to the application password, at least 12 characters. "
            "The API and interface stay closed without it."
        )
    if settings.integration_mode == "live" and settings.live_key_is_dev_default:
        raise RuntimeError(
            "Live mode refuses the development token encryption key. "
            "Set ACWA_TOKEN_ENCRYPTION_KEY to a Fernet key stored outside the database."
        )
    return settings


def clear_settings_cache() -> None:
    get_settings.cache_clear()
