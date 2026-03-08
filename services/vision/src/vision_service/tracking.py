from __future__ import annotations

from dataclasses import dataclass, field
from uuid import uuid4

import numpy as np

from .domain import ClosedTrack, Detection, MockVideoSource, TrackObservation, utcnow_iso


def _compute_iou(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    inter_x1 = max(ax1, bx1)
    inter_y1 = max(ay1, by1)
    inter_x2 = min(ax2, bx2)
    inter_y2 = min(ay2, by2)
    inter_w = max(0, inter_x2 - inter_x1)
    inter_h = max(0, inter_y2 - inter_y1)
    if inter_w == 0 or inter_h == 0:
        return 0.0
    intersection = inter_w * inter_h
    a_area = max(1, (ax2 - ax1) * (ay2 - ay1))
    b_area = max(1, (bx2 - bx1) * (by2 - by1))
    return intersection / float(a_area + b_area - intersection)


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


@dataclass(slots=True)
class _ActiveTrack:
    id: str
    source: MockVideoSource
    label: str
    detector_label: str
    observations: list[TrackObservation] = field(default_factory=list)
    max_confidence: float = 0.0
    confidence_sum: float = 0.0
    last_frame_index: int = 0

    def update(
        self,
        *,
        frame_index: int,
        offset_ms: int,
        detection: Detection,
        frame_bgr: np.ndarray,
    ) -> None:
        observation = TrackObservation(
            frame_index=frame_index,
            offset_ms=offset_ms,
            captured_at=utcnow_iso(),
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


class SimpleTrackManager:
    def __init__(
        self,
        *,
        source: MockVideoSource,
        iou_threshold: float,
        max_gap_frames: int,
    ) -> None:
        self._source = source
        self._iou_threshold = iou_threshold
        self._max_gap_frames = max_gap_frames
        self._active_tracks: dict[str, _ActiveTrack] = {}

    def update(
        self,
        *,
        frame_index: int,
        offset_ms: int,
        detections: list[Detection],
        frame_bgr: np.ndarray,
    ) -> list[ClosedTrack]:
        closed: list[ClosedTrack] = []
        unmatched_track_ids = set(self._active_tracks.keys())
        unmatched_detection_indices = set(range(len(detections)))

        candidate_pairs: list[tuple[float, str, int]] = []
        for track_id, track in self._active_tracks.items():
            last_bbox = track.observations[-1].bbox if track.observations else None
            if last_bbox is None:
                continue
            for detection_index, detection in enumerate(detections):
                if detection.label != track.label:
                    continue
                iou = _compute_iou(last_bbox, detection.bbox)
                if iou >= self._iou_threshold:
                    candidate_pairs.append((iou, track_id, detection_index))

        for _, track_id, detection_index in sorted(candidate_pairs, reverse=True):
            if track_id not in unmatched_track_ids or detection_index not in unmatched_detection_indices:
                continue
            track = self._active_tracks[track_id]
            track.update(
                frame_index=frame_index,
                offset_ms=offset_ms,
                detection=detections[detection_index],
                frame_bgr=frame_bgr,
            )
            unmatched_track_ids.discard(track_id)
            unmatched_detection_indices.discard(detection_index)

        for detection_index in sorted(unmatched_detection_indices):
            detection = detections[detection_index]
            track_id = f"trk-{uuid4().hex[:10]}"
            track = _ActiveTrack(
                id=track_id,
                source=self._source,
                label=detection.label,
                detector_label=detection.detector_label,
            )
            track.update(
                frame_index=frame_index,
                offset_ms=offset_ms,
                detection=detection,
                frame_bgr=frame_bgr,
            )
            self._active_tracks[track_id] = track

        expired_track_ids = [
            track_id
            for track_id, track in self._active_tracks.items()
            if frame_index - track.last_frame_index > self._max_gap_frames
        ]
        for track_id in expired_track_ids:
            closed.append(self._active_tracks.pop(track_id).close("track-gap"))

        return closed

    def finalize(self) -> list[ClosedTrack]:
        closed = [track.close("end-of-source") for track in self._active_tracks.values()]
        self._active_tracks.clear()
        return closed
