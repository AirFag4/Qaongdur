from __future__ import annotations

from functools import lru_cache
from pathlib import Path

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
    default_site_id: str = "site-local-01"
    mock_video_dir: str = "./mock-videos"
    data_dir: str = "./data"
    database_path: str = "./data/vision.sqlite3"
    artifacts_dir: str = "./data/artifacts"
    detector_model_name: str = "yolov8n.pt"
    detector_confidence_threshold: float = 0.35
    sample_fps: float = 2.0
    min_sample_fps: float = 1.0
    max_sample_fps: float = 3.0
    tracker_iou_threshold: float = 0.3
    tracker_max_gap_frames: int = 3
    storage_limit_bytes: int = 10 * 1024 * 1024 * 1024
    crop_jpeg_quality: int = 85
    crop_max_dimension: int = 320
    embedding_enabled: bool = True
    embedding_model_name: str = "MobileCLIP2-S0"
    face_enabled: bool = True
    face_min_track_seconds: float = 2.0
    face_model_name: str = "InspireFace-small"

    def ensure_directories(self) -> None:
        Path(self.data_dir).mkdir(parents=True, exist_ok=True)
        Path(self.artifacts_dir).mkdir(parents=True, exist_ok=True)
        Path(self.database_path).parent.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_directories()
    return settings
