from __future__ import annotations

import json
from functools import lru_cache
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="QAONGDUR_",
        env_file=".env",
        case_sensitive=False,
    )

    env: str = "development"
    service_name: str = "qaongdur-control-api"
    control_api_host: str = "0.0.0.0"
    control_api_port: int = 8000
    control_api_cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:5173"]
    )
    keycloak_issuer_url: str = "http://localhost:8080/realms/qaongdur-dev"
    keycloak_discovery_url: str | None = None
    keycloak_audience: str = "qaongdur-control-api"
    keycloak_web_client_id: str = "qaongdur-web"
    keycloak_expected_algorithms: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["RS256"]
    )
    keycloak_step_up_acr: str = "urn:qaongdur:loa:2"
    oidc_cache_ttl_seconds: int = 300
    camera_store_path: str = "./data/cameras.json"
    default_site_id: str = "site-local-01"
    default_site_code: str = "LOCAL-01"
    default_site_name: str = "Local Camera Lab"
    default_site_region: str = "Local"
    mock_video_dir: str | None = None
    mock_video_path_prefix: str = "mock-video"
    mock_video_zone: str = "Mock Video Lab"
    mock_video_rtsp_base_url: str = "rtsp://mediamtx:8554"
    mock_video_max_sources: int = 1
    mediamtx_api_url: str = "http://mediamtx:9997"
    mediamtx_api_user: str = "qaongdur-api"
    mediamtx_api_password: str = "qaongdur-api"
    mediamtx_hls_public_url: str = "http://localhost:8888"
    mediamtx_playback_internal_url: str = "http://mediamtx:9996"
    mediamtx_playback_public_url: str = "http://localhost:9996"
    mediamtx_record_segment_duration_seconds: int = 30
    vision_service_url: str = "http://localhost:8010"
    internal_service_token: str = "qaongdur-internal-dev"

    @field_validator(
        "control_api_cors_origins",
        "keycloak_expected_algorithms",
        mode="before",
    )
    @classmethod
    def _split_csv(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            value = value.strip()
            if not value:
                return []
            if value.startswith("["):
                return [
                    part.strip()
                    for part in json.loads(value)
                    if isinstance(part, str) and part.strip()
                ]
            return [part.strip() for part in value.split(",") if part.strip()]
        return value


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
