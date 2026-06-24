"""Application settings, loaded from environment / .env."""
from __future__ import annotations

from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Core
    environment: str = "development"
    secret_key: str = "change-me"
    api_v1_prefix: str = "/api/v1"
    project_name: str = "FlowCare AI"
    # Comma-separated allowed origins for CORS, or "*" for any.
    cors_origins: str = "*"

    # Database
    database_url: str = "postgresql+psycopg://flowcare:flowcare@localhost:5432/flowcare"

    # Redis / Celery
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    # Auth
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    jwt_algorithm: str = "HS256"

    # AI
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-opus-4-8"

    # Storage
    storage_backend: str = "local"  # local | s3
    storage_local_dir: str = "./var/uploads"
    s3_endpoint_url: str | None = None
    s3_bucket: str = "flowcare-referrals"
    s3_access_key: str | None = None
    s3_secret_key: str | None = None

    # OCR
    ocr_backend: str = "tesseract"  # tesseract | textract
    tesseract_cmd: str | None = None

    # Notifications — Twilio SMS
    twilio_account_sid: str | None = None
    twilio_auth_token: str | None = None
    twilio_from_number: str | None = None  # E.164, e.g. +14155552671
    twilio_messaging_service_sid: str | None = None  # alternative to from_number
    twilio_base_url: str = "https://api.twilio.com"
    twilio_timeout_seconds: float = 10.0

    # Email (SMTP) — leave blank to use the logged mock sender
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_from: str = "FlowCare AI <no-reply@flowcare.ai>"
    smtp_use_tls: bool = True
    frontend_base_url: str = "http://localhost:3000"

    # Seed admin
    first_admin_email: str = "admin@flowcare.ai"
    first_admin_password: str = "admin12345"

    @field_validator("database_url")
    @classmethod
    def _normalize_db_url(cls, v: str) -> str:
        # Managed Postgres (Render/Heroku/etc.) hand out postgres:// or
        # postgresql:// URLs; pin them to the psycopg v3 driver we use.
        for prefix in ("postgresql+psycopg://", "sqlite"):
            if v.startswith(prefix):
                return v
        if v.startswith("postgres://"):
            return "postgresql+psycopg://" + v[len("postgres://"):]
        if v.startswith("postgresql://"):
            return "postgresql+psycopg://" + v[len("postgresql://"):]
        return v

    @property
    def is_production(self) -> bool:
        return self.environment.lower() in {"production", "prod"}

    @property
    def has_llm(self) -> bool:
        return bool(self.anthropic_api_key)

    @property
    def cors_origin_list(self) -> list[str]:
        if self.cors_origins.strip() == "*":
            return ["*"]
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def has_twilio(self) -> bool:
        return bool(
            self.twilio_account_sid
            and self.twilio_auth_token
            and (self.twilio_from_number or self.twilio_messaging_service_sid)
        )

    @property
    def has_smtp(self) -> bool:
        return bool(self.smtp_host)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
