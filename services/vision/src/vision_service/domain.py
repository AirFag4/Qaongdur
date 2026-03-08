from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

import numpy as np


def utcnow_iso() -> str:
    return datetime.now(tz=UTC).isoformat()


@dataclass(slots=True)
class VisionSource:
    id: str
    site_id: str
    camera_id: str
    camera_name: str
    path_name: str
    stream_url: str
    live_stream_url: str | None = None
    capture_mode: str = "recording-segment"
    source_kind: str = "rtsp"
    ingest_mode: str = "pull"
    health: str = "offline"
    file_path: str = ""
    duration_sec: float = 0.0
    frame_width: int = 0
    frame_height: int = 0
    source_fps: float = 0.0


MockVideoSource = VisionSource


@dataclass(slots=True)
class Detection:
    label: str
    detector_label: str
    confidence: float
    x1: int
    y1: int
    x2: int
    y2: int

    @property
    def bbox(self) -> tuple[int, int, int, int]:
        return (self.x1, self.y1, self.x2, self.y2)


@dataclass(slots=True)
class TrackObservation:
    frame_index: int
    offset_ms: int
    captured_at: str
    confidence: float
    bbox: tuple[int, int, int, int]
    crop_bgr: np.ndarray


@dataclass(slots=True)
class ClosedTrack:
    id: str
    source: MockVideoSource
    label: str
    detector_label: str
    observations: list[TrackObservation]
    max_confidence: float
    avg_confidence: float
    closed_reason: str
    created_at: str = field(default_factory=utcnow_iso)

    @property
    def frame_count(self) -> int:
        return len(self.observations)

    @property
    def duration_seconds(self) -> float:
        if not self.observations:
            return 0.0
        return max(
            0.0,
            (self.observations[-1].offset_ms - self.observations[0].offset_ms) / 1000.0,
        )

    def first_observation(self) -> TrackObservation:
        return self.observations[0]

    def middle_observation(self) -> TrackObservation:
        return self.observations[len(self.observations) // 2]

    def last_observation(self) -> TrackObservation:
        return self.observations[-1]
