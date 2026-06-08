from __future__ import annotations

from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

LLMProvider = Literal["openai", "anthropic"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Database
    postgres_host: str = "db"
    postgres_port: int = 5432
    postgres_db: str = "sears_voice"
    postgres_user: str = "sears"
    postgres_password: str = "changeme"

    # LLM providers — set VOICE_LLM_PROVIDER / VISION_LLM_PROVIDER to "openai" or "anthropic"
    voice_llm_provider: LLMProvider = "openai"
    vision_llm_provider: LLMProvider = "openai"
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    openai_realtime_model: str = "gpt-4o-realtime-preview"
    openai_vision_model: str = "gpt-4o"
    anthropic_model: str = "claude-haiku-4-5-20251001"

    # Twilio
    twilio_account_sid: str
    twilio_auth_token: str
    twilio_phone_number: str
    twilio_api_key_sid: str = ""
    twilio_api_key_secret: str = ""
    twilio_twiml_app_sid: str = ""

    # App
    base_url: str
    app_env: str = "development"
    secret_key: str = "changeme-32-chars-minimum"
    log_level: str = "INFO"

    # Tier 3 — Visual Diagnosis
    sendgrid_api_key: str = ""
    from_email: str = "alex@sears-voice.example.com"
    upload_link_ttl_hours: int = 24

    @model_validator(mode="after")
    def validate_provider_keys(self) -> Settings:
        if self.voice_llm_provider == "openai" and not self.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required when VOICE_LLM_PROVIDER=openai")
        if self.voice_llm_provider == "anthropic" and not self.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY is required when VOICE_LLM_PROVIDER=anthropic")
        if self.vision_llm_provider == "openai" and not self.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required when VISION_LLM_PROVIDER=openai")
        if self.vision_llm_provider == "anthropic" and not self.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY is required when VISION_LLM_PROVIDER=anthropic")
        return self

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def database_url_sync(self) -> str:
        """Synchronous URL used by Alembic offline migrations."""
        return (
            f"postgresql+psycopg2://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


settings = Settings()
