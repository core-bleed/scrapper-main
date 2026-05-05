from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    db_path: Path = Field(default=Path("./sdr.db"), validation_alias="SDR_DB_PATH")
    apollo_api_key: str | None = Field(default=None, validation_alias="APOLLO_API_KEY")
    hunter_api_key: str | None = Field(default=None, validation_alias="HUNTER_API_KEY")
    product_hunt_access_token: str | None = Field(
        default=None, validation_alias="PRODUCT_HUNT_ACCESS_TOKEN"
    )
    yc_request_delay: float = Field(default=0.5, validation_alias="SDR_YC_REQUEST_DELAY")
    user_agent: str = Field(
        default="Mozilla/5.0 (compatible; SDR-Scraper/0.1)",
        validation_alias="SDR_USER_AGENT",
    )


def get_settings() -> Settings:
    return Settings()
