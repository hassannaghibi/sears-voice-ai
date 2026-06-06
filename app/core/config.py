from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Database
    postgres_host: str = "db"
    postgres_port: int = 5432
    postgres_db: str = "sears_voice"
    postgres_user: str = "sears"
    postgres_password: str = "changeme"

    # OpenAI
    openai_api_key: str

    # Twilio
    twilio_account_sid: str
    twilio_auth_token: str
    twilio_phone_number: str

    # App
    base_url: str
    app_env: str = "development"
    secret_key: str = "changeme-32-chars-minimum"
    log_level: str = "INFO"

    # Tier 3 — Visual Diagnosis
    sendgrid_api_key: str = ""
    from_email: str = "alex@sears-voice.example.com"
    upload_link_ttl_hours: int = 24

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
