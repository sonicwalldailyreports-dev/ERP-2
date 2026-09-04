from functools import lru_cache
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_SECRET_KEY = "development-only-secret-change-me-32-bytes"


class Settings(BaseSettings):
    app_name: str = "Small Office Management Software"
    environment: Literal["development", "test", "production"] = "development"
    debug: bool = False
    api_prefix: str = "/api/v1"
    # This value is intentionally usable only for local development/tests.
    # Production validation below rejects it even though it is long enough.
    secret_key: str = DEFAULT_SECRET_KEY
    database_url: str = "sqlite+aiosqlite:///./small_office.db"
    redis_url: str = "redis://localhost:6379/0"
    task_queue_backend: Literal["in_process", "redis"] = "in_process"
    task_queue_max_retries: int = 3
    task_queue_retry_delay_seconds: int = 30
    email_enabled: bool = False
    email_from: str = "noreply@example.com"
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_use_tls: bool = True
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:8080"]
    log_level: str = "INFO"
    access_token_minutes: int = 15
    refresh_token_days: int = 30
    max_failed_logins: int = 5
    lockout_minutes: int = 15
    password_reset_minutes: int = 30
    dev_user_header_enabled: bool = False
    dev_user_header_loopback_only: bool = True

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="",
        extra="ignore",
        case_sensitive=False,
    )

    @model_validator(mode="after")
    def validate_security_settings(self) -> "Settings":
        if self.environment == "production":
            if self.secret_key == DEFAULT_SECRET_KEY:
                raise ValueError("SECRET_KEY must be explicitly configured in production.")
            if len(self.secret_key) < 32:
                raise ValueError("SECRET_KEY must contain at least 32 characters in production.")
            if len(set(self.secret_key)) < 16:
                raise ValueError("SECRET_KEY must contain sufficient entropy in production.")
            if self.dev_user_header_enabled:
                raise ValueError("Development user headers cannot be enabled in production.")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
