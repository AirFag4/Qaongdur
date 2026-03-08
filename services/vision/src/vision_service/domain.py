from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

import numpy as np


def utcnow_iso() -> str:
    return datetime.now(tz=UTC).isoformat()


@dataclass(slots=True)
class MockVideoSource:
    id: str
    site_id: str
    camera_id: str
    camera_name: str
    file_path: str
    path_name: str
    stream_url: str
    capture_mode: str
    duration_sec: float
    frame_width: int
    frame_height: int
    source_fps: float


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
