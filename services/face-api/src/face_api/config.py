from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="QAONGDUR_FACE_",
        env_file=".env",
        case_sensitive=False,
    )

    env: str = "development"
    service_host: str = "0.0.0.0"
    service_port: int = 8020
    runtime_dir: str = "/runtime"
    bootstrap_error_file: str = "/runtime/bootstrap-error.txt"
    inspireface_repo: str = "/mnt/inspireface"
    resource_path: str = "/mnt/inspireface/test_res/pack/Megatron"
    model_name: str = "Megatron"

    def ensure_directories(self) -> None:
        Path(self.runtime_dir).mkdir(parents=True, exist_ok=True)
        Path(self.bootstrap_error_file).parent.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_directories()
    return settings
