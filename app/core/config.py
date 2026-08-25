from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any

from pydantic import BeforeValidator, Field, SecretStr
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


def _parse_origins(value: Any) -> list[str]:
    if isinstance(value, list):
        return value
    if not value:
        return []
    if isinstance(value, str):
        value = value.strip()
        if value.startswith("["):
            import json

            return json.loads(value)
        return [origin.strip() for origin in value.split(",") if origin.strip()]
    raise ValueError("CORS_ORIGINS must be a JSON array or comma-separated string")


Origins = Annotated[list[str], NoDecode, BeforeValidator(_parse_origins)]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "Alfateks Textile Warehouse API"
    environment: str = "development"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"

    database_url: str = "postgresql+asyncpg://alfateks:alfateks@db:5432/alfateks"
    jwt_secret_key: SecretStr = Field(min_length=32)
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = Field(default=60, ge=5, le=1440)
    jwt_issuer: str = "alfateks-api"
    jwt_audience: str = "alfateks-clients"
    activity_update_minutes: int = Field(default=5, ge=1, le=60)
    login_rate_limit_attempts: int = Field(default=5, ge=2, le=100)
    login_rate_limit_minutes: int = Field(default=15, ge=1, le=1440)
    audit_max_page_size: int = Field(default=100, ge=10, le=500)
    audit_max_range_days: int = Field(default=366, ge=1, le=3660)
    cors_origins: Origins = Field(default_factory=list)
    allow_negative_stock: bool = False
    media_root: Path = Path("media")
    max_product_image_bytes: int = Field(default=5 * 1024 * 1024, ge=1024)
    max_product_image_pixels: int = Field(default=24_000_000, ge=1_000_000)
    product_image_max_dimension: int = Field(default=2000, ge=512, le=6000)
    ocr_languages: str = "eng+tur+rus+uzb"
    ocr_timeout_seconds: int = Field(default=20, ge=5, le=60)
    report_timezone: str = "Europe/Istanbul"
    report_max_export_rows: int = Field(default=5000, ge=1, le=50_000)
    report_png_max_rows: int = Field(default=200, ge=1, le=1000)


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
