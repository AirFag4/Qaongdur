from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="QAONGDUR_VISION_",
        env_file=".env",
        case_sensitive=False,
    )

    env: str = "development"
    service_host: str = "0.0.0.0"
    service_port: int = 8010
    sample_mode: bool = True
    storage_bucket: str = "qaongdur-dev"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
