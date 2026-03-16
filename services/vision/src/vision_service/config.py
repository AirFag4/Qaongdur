from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import field_validator, model_validator
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
    control_api_url: str = "http://control-api:8000"
    internal_service_token: str = "qaongdur-internal-dev"
    mock_video_dir: str = "./mock-videos"
    mock_video_rtsp_base_url: str = "rtsp://mediamtx:8554"
    mock_video_path_prefix: str = "mock-video"
    mock_video_use_vms: bool = True
    mock_video_max_sources: int = 1
    recordings_dir: str = "/recordings"
    segment_poll_interval_seconds: float = 10.0
    segment_min_age_seconds: float = 5.0
    segment_worker_count: int = 1
    data_dir: str = "./data"
    database_path: str = "./data/vision.sqlite3"
    artifacts_dir: str = "./data/artifacts"
    detector_model_name: str = "yolo26n.pt"
    detector_confidence_threshold: float = 0.35
    sample_fps: float = 2.0
    min_sample_fps: float = 1.0
    max_sample_fps: float = 3.0
    tracker_activation_threshold: float = 0.35
    tracker_matching_threshold: float = 0.8
    tracker_lost_buffer_frames: int = 6
    tracker_minimum_consecutive_frames: int = 1
    tracker_max_gap_frames: int = 6
    storage_limit_bytes: int | None = None
    storage_total_limit_bytes: int = 10 * 1024 * 1024 * 1024
    storage_recording_share_percent: int = 80
    crop_jpeg_quality: int = 85
    crop_max_dimension: int = 320
    frame_max_dimension: int = 960
    embedding_enabled: bool = True
    embedding_model_name: str = "MobileCLIP2-S0"
    face_enabled: bool = True
    face_min_track_seconds: float = 2.0
    face_model_name: str = "Megatron"
    face_service_url: str = "http://face-api:8020"
    face_request_timeout_seconds: float = 15.0
    vector_store_enabled: bool = True
    vector_store_url: str = "http://qdrant:6333"
    vector_store_timeout_seconds: float = 10.0
    vector_store_object_collection: str = "qaongdur-object-embeddings"
    vector_store_face_collection: str = "qaongdur-face-embeddings"
    purge_retired_mock_history: bool = False

    @field_validator("storage_recording_share_percent")
    @classmethod
    def _validate_storage_recording_share_percent(cls, value: int) -> int:
        if value <= 0 or value >= 100:
            raise ValueError("storage_recording_share_percent must be between 1 and 99")
        return value

    @model_validator(mode="after")
    def _validate_storage_totals(self) -> "Settings":
        if self.storage_total_limit_bytes <= 0:
            raise ValueError("storage_total_limit_bytes must be positive")
        if self.storage_limit_bytes is not None and self.storage_limit_bytes <= 0:
            raise ValueError("storage_limit_bytes must be positive when provided")
        return self

    @property
    def artifact_storage_share_percent(self) -> int:
        return 100 - self.storage_recording_share_percent

    @property
    def effective_storage_limit_bytes(self) -> int:
        if self.storage_limit_bytes is not None:
            return self.storage_limit_bytes

        recording_bytes = (
            self.storage_total_limit_bytes * self.storage_recording_share_percent
        ) // 100
        return self.storage_total_limit_bytes - recording_bytes

    def ensure_directories(self) -> None:
        Path(self.data_dir).mkdir(parents=True, exist_ok=True)
        Path(self.artifacts_dir).mkdir(parents=True, exist_ok=True)
        Path(self.database_path).parent.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_directories()
    return settings
