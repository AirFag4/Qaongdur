from __future__ import annotations

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


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
    control_api_cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:5173"]
    )
    keycloak_issuer_url: str = "http://localhost:8080/realms/qaongdur-dev"
    keycloak_discovery_url: str | None = None
    keycloak_audience: str = "qaongdur-control-api"
    keycloak_web_client_id: str = "qaongdur-web"
    keycloak_expected_algorithms: list[str] = Field(default_factory=lambda: ["RS256"])
    keycloak_step_up_acr: str = "urn:qaongdur:loa:2"
    oidc_cache_ttl_seconds: int = 300

    @field_validator(
        "control_api_cors_origins",
        "keycloak_expected_algorithms",
        mode="before",
    )
    @classmethod
    def _split_csv(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            return [part.strip() for part in value.split(",") if part.strip()]
        return value


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
