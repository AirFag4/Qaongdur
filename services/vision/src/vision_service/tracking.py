from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from uuid import uuid4

import numpy as np
import supervision as sv

from .domain import ClosedTrack, Detection, TrackObservation, VisionSource

TRACK_LABELS = ("person", "vehicle")
TRACK_CLASS_IDS = {
    "person": 0,
    "vehicle": 1,
}


def _crop_frame(
    frame_bgr: np.ndarray,
    bbox: tuple[int, int, int, int],
) -> np.ndarray:
    height, width = frame_bgr.shape[:2]
    x1, y1, x2, y2 = bbox
    x1 = max(0, min(width - 1, x1))
    y1 = max(0, min(height - 1, y1))
    x2 = max(x1 + 1, min(width, x2))
    y2 = max(y1 + 1, min(height, y2))
    return frame_bgr[y1:y2, x1:x2].copy()


def _empty_detections() -> sv.Detections:
    return sv.Detections(
        xyxy=np.empty((0, 4), dtype=np.float32),
        confidence=np.empty((0,), dtype=np.float32),
        class_id=np.empty((0,), dtype=np.int32),
    )


def _to_supervision_detections(
    *,
    label: str,
    detections: list[Detection],
) -> sv.Detections:
    if not detections:
        return _empty_detections()

    return sv.Detections(
        xyxy=np.asarray([detection.bbox for detection in detections], dtype=np.float32),
        confidence=np.asarray(
            [detection.confidence for detection in detections],
            dtype=np.float32,
        ),
        class_id=np.full(
            len(detections),
            TRACK_CLASS_IDS[label],
            dtype=np.int32,
        ),
        data={
            "source_index": np.arange(len(detections), dtype=np.int32),
            "detector_label": np.asarray(
                [detection.detector_label for detection in detections],
                dtype=object,
            ),
        },
    )


@dataclass(slots=True)
class _ActiveTrack:
    id: str
    source: VisionSource
    label: str
    detector_label: str
    external_tracker_id: int
    observations: list[TrackObservation] = field(default_factory=list)
    max_confidence: float = 0.0
    confidence_sum: float = 0.0
    last_frame_index: int = 0

    def update(
        self,
        *,
        frame_index: int,
        offset_ms: int,
        captured_at: str,
        detection: Detection,
        frame_bgr: np.ndarray,
    ) -> None:
        observation = TrackObservation(
            frame_index=frame_index,
            offset_ms=offset_ms,
            captured_at=captured_at,
            confidence=detection.confidence,
            bbox=detection.bbox,
            crop_bgr=_crop_frame(frame_bgr, detection.bbox),
        )
        self.observations.append(observation)
        self.max_confidence = max(self.max_confidence, detection.confidence)
        self.confidence_sum += detection.confidence
        self.last_frame_index = frame_index
        self.detector_label = detection.detector_label

    def close(self, reason: str) -> ClosedTrack:
        return ClosedTrack(
            id=self.id,
            source=self.source,
            label=self.label,
            detector_label=self.detector_label,
            observations=self.observations,
            max_confidence=self.max_confidence,
            avg_confidence=(self.confidence_sum / len(self.observations))
            if self.observations
            else 0.0,
            closed_reason=reason,
        )


class ByteTrackManager:
    def __init__(
        self,
        *,
        source: VisionSource,
        activation_threshold: float,
        matching_threshold: float,
        lost_buffer_frames: int,
        minimum_consecutive_frames: int,
        max_gap_frames: int,
        frame_rate: float,
    ) -> None:
        tracker_frame_rate = max(int(round(frame_rate)), 1)
        self._source = source
        self._max_gap_frames = max(max_gap_frames, 1)
        self._trackers = {
            label: sv.ByteTrack(
                track_activation_threshold=activation_threshold,
                lost_track_buffer=max(lost_buffer_frames, self._max_gap_frames),
                minimum_matching_threshold=matching_threshold,
                frame_rate=tracker_frame_rate,
                minimum_consecutive_frames=minimum_consecutive_frames,
            )
            for label in TRACK_LABELS
        }
        self._active_tracks: dict[tuple[str, int], _ActiveTrack] = {}

    def update(
        self,
        *,
        frame_index: int,
        offset_ms: int,
        captured_at: str,
        detections: list[Detection],
        frame_bgr: np.ndarray,
    ) -> list[ClosedTrack]:
        grouped_detections: dict[str, list[Detection]] = defaultdict(list)
        for detection in detections:
            if detection.label in TRACK_CLASS_IDS:
                grouped_detections[detection.label].append(detection)

        updated_keys: set[tuple[str, int]] = set()
        for label, tracker in self._trackers.items():
            label_detections = grouped_detections.get(label, [])
            tracked_detections = tracker.update_with_detections(
                _to_supervision_detections(
                    label=label,
                    detections=label_detections,
                )
            )
            if len(tracked_detections) == 0 or tracked_detections.tracker_id is None:
                continue

            source_indices = tracked_detections.data.get("source_index", [])
            for tracked_index, tracker_id in enumerate(tracked_detections.tracker_id.tolist()):
                source_index = int(source_indices[tracked_index])
                detection = label_detections[source_index]
                key = (label, int(tracker_id))
                track = self._active_tracks.get(key)
                if track is None:
                    track = _ActiveTrack(
                        id=f"trk-{uuid4().hex[:10]}",
                        source=self._source,
                        label=label,
                        detector_label=detection.detector_label,
                        external_tracker_id=int(tracker_id),
                    )
                    self._active_tracks[key] = track
                track.update(
                    frame_index=frame_index,
                    offset_ms=offset_ms,
                    captured_at=captured_at,
                    detection=detection,
                    frame_bgr=frame_bgr,
                )
                updated_keys.add(key)

        closed: list[ClosedTrack] = []
        stale_keys = [
            key
            for key, track in self._active_tracks.items()
            if key not in updated_keys and frame_index - track.last_frame_index > self._max_gap_frames
        ]
        for key in stale_keys:
            closed.append(self._active_tracks.pop(key).close("track-gap"))
        return closed

    def finalize(self) -> list[ClosedTrack]:
        closed = [track.close("end-of-source") for track in self._active_tracks.values()]
        self._active_tracks.clear()
        for tracker in self._trackers.values():
            tracker.reset()
        return closed
