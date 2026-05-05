from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = Field(
        default="postgresql+asyncpg://sdr:sdr@localhost:5432/sdr",
        validation_alias="DATABASE_URL",
    )
    redis_url: str = Field(default="redis://localhost:6379/0", validation_alias="REDIS_URL")

    verifier_provider: str = Field(default="own_api", validation_alias="VERIFIER_PROVIDER")
    own_verifier_url: str | None = Field(default=None, validation_alias="OWN_VERIFIER_URL")
    own_verifier_api_key: str | None = Field(
        default=None, validation_alias="OWN_VERIFIER_API_KEY"
    )
    millionverifier_api_key: str | None = Field(
        default=None, validation_alias="MILLIONVERIFIER_API_KEY"
    )
    hunter_api_key: str | None = Field(default=None, validation_alias="HUNTER_API_KEY")

    apollo_api_key: str | None = Field(default=None, validation_alias="APOLLO_API_KEY")
    product_hunt_access_token: str | None = Field(
        default=None, validation_alias="PRODUCT_HUNT_ACCESS_TOKEN"
    )
    yc_request_delay: float = Field(default=0.5, validation_alias="SDR_YC_REQUEST_DELAY")
    user_agent: str = Field(
        default="Mozilla/5.0 (compatible; SDR-Scraper/0.1)",
        validation_alias="SDR_USER_AGENT",
    )

    sqlite_legacy_path: Path = Field(
        default=Path("./sdr.db"),
        validation_alias="SDR_DB_PATH",
        description="SQLite path for migrate_sqlite.py and legacy scraper CLI",
    )


def get_settings() -> Settings:
    return Settings()
