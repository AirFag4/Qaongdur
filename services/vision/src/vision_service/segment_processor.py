from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from threading import Lock
import time

import cv2

from .artifact_store import ArtifactStore
from .config import Settings
from .domain import ClosedTrack, VisionSource, utcnow_iso
from .embedding import CropEmbedder, EmbeddingResult
from .face import FaceEmbedder, FaceEmbeddingResult
from .tracking import ByteTrackManager
from .vector_store import QdrantVectorStore


def _point_from_bbox(bbox: tuple[int, int, int, int]) -> dict[str, int]:
    x1, y1, x2, y2 = bbox
    return {
        "x": int((x1 + x2) / 2),
        "y": int((y1 + y2) / 2),
    }


@dataclass(slots=True)
class PreparedArtifact:
    role: str
    kind: str
    mime_type: str
    payload: bytes


@dataclass(slots=True)
class PreparedTrackBundle:
    track_row: dict[str, object]
    artifacts: list[PreparedArtifact]
    embedding: dict[str, object]
    face_embedding: dict[str, object] | None


@dataclass(slots=True)
class SegmentProcessingMetrics:
    frames_decoded: int = 0
    frames_sampled: int = 0
    tracks_closed: int = 0
    duration_ms: int = 0


@dataclass(slots=True)
class SegmentProcessingResult:
    duration_sec: float
    track_bundles: list[PreparedTrackBundle]
    metrics: SegmentProcessingMetrics


class SegmentProcessor:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._artifact_store = ArtifactStore(
            artifacts_dir=settings.artifacts_dir,
            crop_jpeg_quality=settings.crop_jpeg_quality,
            crop_max_dimension=settings.crop_max_dimension,
            frame_max_dimension=settings.frame_max_dimension,
        )
        from .detection import ObjectDetector

        self._detector = ObjectDetector(
            model_name=settings.detector_model_name,
            confidence_threshold=settings.detector_confidence_threshold,
            device=settings.detector_device,
        )
        self._embedder = CropEmbedder(
            enabled=settings.embedding_enabled,
            model_name=settings.embedding_model_name,
            device=settings.embedding_device,
        )
        self._face_embedder = FaceEmbedder(
            enabled=settings.face_enabled,
            model_name=settings.face_model_name,
            minimum_track_seconds=settings.face_min_track_seconds,
            service_url=settings.face_service_url,
            request_timeout_seconds=settings.face_request_timeout_seconds,
        )
        self._vector_store = QdrantVectorStore(
            enabled=settings.vector_store_enabled,
            base_url=settings.vector_store_url,
            object_collection=settings.vector_store_object_collection,
            face_collection=settings.vector_store_face_collection,
            timeout_seconds=settings.vector_store_timeout_seconds,
        )
        self._detector_lock = Lock()
        self._embedding_lock = Lock()
        self._vector_store_lock = Lock()

    def process_segment(
        self,
        *,
        job_id: str,
        source: VisionSource,
        sample_fps: float,
        segment_path: str,
        segment_start_at: str,
    ) -> SegmentProcessingResult:
        started_monotonic = time.monotonic()
        capture = cv2.VideoCapture(segment_path)
        if not capture.isOpened():
            raise RuntimeError(f"Unable to open recording chunk: {segment_path}")

        try:
            capture_fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
            if capture_fps <= 0:
                capture_fps = source.source_fps if source.source_fps > 0 else sample_fps
            total_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
            estimated_duration_sec = (
                float(total_frames / capture_fps)
                if total_frames > 0 and capture_fps > 0
                else 0.0
            )
            sample_interval_ms = (1000.0 / sample_fps) if sample_fps > 0 else 0.0
            next_sample_offset_ms = 0.0
            segment_start_dt = datetime.fromisoformat(segment_start_at.replace("Z", "+00:00"))
            tracker = ByteTrackManager(
                source=source,
                activation_threshold=self._settings.tracker_activation_threshold,
                matching_threshold=self._settings.tracker_matching_threshold,
                lost_buffer_frames=self._settings.tracker_lost_buffer_frames,
                minimum_consecutive_frames=self._settings.tracker_minimum_consecutive_frames,
                max_gap_frames=self._settings.tracker_max_gap_frames,
                frame_rate=sample_fps,
            )

            frame_index = -1
            last_offset_ms = 0
            metrics = SegmentProcessingMetrics()
            bundles: list[PreparedTrackBundle] = []
            while True:
                ok, frame_bgr = capture.read()
                if not ok:
                    break
                frame_index += 1
                metrics.frames_decoded += 1

                offset_ms = int(capture.get(cv2.CAP_PROP_POS_MSEC) or 0)
                if capture_fps > 0:
                    offset_ms = int((frame_index / capture_fps) * 1000)
                if sample_interval_ms > 0 and offset_ms + 0.5 < next_sample_offset_ms:
                    continue

                metrics.frames_sampled += 1
                if sample_interval_ms > 0:
                    next_sample_offset_ms += sample_interval_ms
                    while next_sample_offset_ms <= offset_ms:
                        next_sample_offset_ms += sample_interval_ms
                last_offset_ms = max(last_offset_ms, offset_ms)
                captured_at = (segment_start_dt + timedelta(milliseconds=offset_ms)).astimezone(
                    UTC
                ).isoformat()
                with self._detector_lock:
                    detections = self._detector.detect(frame_bgr)
                closed_tracks = tracker.update(
                    frame_index=frame_index,
                    offset_ms=offset_ms,
                    captured_at=captured_at,
                    detections=detections,
                    frame_bgr=frame_bgr,
                )
                for closed_track in closed_tracks:
                    bundles.append(
                        self._build_track_bundle(
                            job_id=job_id,
                            track=closed_track,
                            sample_fps=sample_fps,
                            segment_path=segment_path,
                            segment_start_at=segment_start_at,
                            segment_duration_sec=max(
                                estimated_duration_sec,
                                last_offset_ms / 1000.0,
                            ),
                        )
                    )
                    metrics.tracks_closed += 1

            final_duration_sec = max(estimated_duration_sec, last_offset_ms / 1000.0)
            for closed_track in tracker.finalize():
                bundles.append(
                    self._build_track_bundle(
                        job_id=job_id,
                        track=closed_track,
                        sample_fps=sample_fps,
                        segment_path=segment_path,
                        segment_start_at=segment_start_at,
                        segment_duration_sec=final_duration_sec,
                    )
                )
                metrics.tracks_closed += 1

            metrics.duration_ms = int((time.monotonic() - started_monotonic) * 1000)
            return SegmentProcessingResult(
                duration_sec=final_duration_sec,
                track_bundles=bundles,
                metrics=metrics,
            )
        finally:
            capture.release()

    def _build_track_bundle(
        self,
        *,
        job_id: str,
        track: ClosedTrack,
        sample_fps: float,
        segment_path: str,
        segment_start_at: str,
        segment_duration_sec: float,
    ) -> PreparedTrackBundle:
        first_observation = track.first_observation()
        middle_observation = track.middle_observation()
        last_observation = track.last_observation()
        with self._embedding_lock:
            embedding: EmbeddingResult = self._embedder.embed(middle_observation.crop_bgr)
        face_embedding: FaceEmbeddingResult = self._face_embedder.maybe_embed(
            label=track.label,
            duration_seconds=track.duration_seconds,
            crop_bgr=middle_observation.crop_bgr,
        )

        artifacts = [
            PreparedArtifact(
                role="first",
                kind="crop",
                mime_type="image/jpeg",
                payload=self._artifact_store.encode_crop(first_observation.crop_bgr),
            ),
            PreparedArtifact(
                role="middle",
                kind="crop",
                mime_type="image/jpeg",
                payload=self._artifact_store.encode_crop(middle_observation.crop_bgr),
            ),
            PreparedArtifact(
                role="last",
                kind="crop",
                mime_type="image/jpeg",
                payload=self._artifact_store.encode_crop(last_observation.crop_bgr),
            ),
        ]
        for role, payload in self._encode_observation_frames(
            segment_path=segment_path,
            observations={
                "frame-first": first_observation,
                "frame-middle": middle_observation,
                "frame-last": last_observation,
            },
        ).items():
            artifacts.append(
                PreparedArtifact(
                    role=role,
                    kind="frame",
                    mime_type="image/jpeg",
                    payload=payload,
                )
            )
        for role, payload in {
            "face-detected": face_embedding.detected_face_jpeg,
            "face-aligned": face_embedding.aligned_face_jpeg,
        }.items():
            if payload:
                artifacts.append(
                    PreparedArtifact(
                        role=role,
                        kind="face",
                        mime_type="image/jpeg",
                        payload=payload,
                    )
                )

        with self._vector_store_lock:
            self._vector_store.upsert_object_embedding(
                track_id=track.id,
                source_id=track.source.id,
                camera_id=track.source.camera_id,
                label=track.label,
                captured_at=middle_observation.captured_at,
                vector=embedding.vector,
            )
            if face_embedding.status == "ready" and face_embedding.vector:
                self._vector_store.upsert_face_embedding(
                    track_id=track.id,
                    source_id=track.source.id,
                    camera_id=track.source.camera_id,
                    label=track.label,
                    captured_at=middle_observation.captured_at,
                    vector=face_embedding.vector,
                )

        return PreparedTrackBundle(
            track_row={
                "id": track.id,
                "job_id": job_id,
                "source_id": track.source.id,
                "site_id": track.source.site_id,
                "camera_id": track.source.camera_id,
                "camera_name": track.source.camera_name,
                "label": track.label,
                "detector_label": track.detector_label,
                "first_seen_at": first_observation.captured_at,
                "middle_seen_at": middle_observation.captured_at,
                "last_seen_at": last_observation.captured_at,
                "first_seen_offset_ms": first_observation.offset_ms,
                "middle_seen_offset_ms": middle_observation.offset_ms,
                "last_seen_offset_ms": last_observation.offset_ms,
                "segment_path": segment_path,
                "segment_start_at": segment_start_at,
                "segment_duration_sec": segment_duration_sec,
                "frame_count": track.frame_count,
                "sample_fps": sample_fps,
                "max_confidence": track.max_confidence,
                "avg_confidence": track.avg_confidence,
                "first_bbox_json": json.dumps(first_observation.bbox),
                "middle_bbox_json": json.dumps(middle_observation.bbox),
                "last_bbox_json": json.dumps(last_observation.bbox),
                "first_point_json": json.dumps(_point_from_bbox(first_observation.bbox)),
                "middle_point_json": json.dumps(_point_from_bbox(middle_observation.bbox)),
                "last_point_json": json.dumps(_point_from_bbox(last_observation.bbox)),
                "embedding_status": embedding.status,
                "embedding_model": embedding.model_name,
                "embedding_dim": len(embedding.vector),
                "face_status": face_embedding.status,
                "face_model": face_embedding.model_name,
                "face_dim": len(face_embedding.vector) if face_embedding.vector else None,
                "face_count": face_embedding.face_count,
                "face_detail": face_embedding.detail,
                "closed_reason": track.closed_reason,
                "created_at": track.created_at,
            },
            artifacts=artifacts,
            embedding={
                "track_id": track.id,
                "model_name": embedding.model_name,
                "vector_json": json.dumps(embedding.vector),
                "created_at": utcnow_iso(),
            },
            face_embedding=(
                {
                    "track_id": track.id,
                    "model_name": face_embedding.model_name,
                    "vector_json": json.dumps(face_embedding.vector)
                    if face_embedding.vector is not None
                    else None,
                    "created_at": utcnow_iso(),
                }
                if face_embedding.status == "ready"
                else None
            ),
        )

    def _encode_observation_frames(
        self,
        *,
        segment_path: str,
        observations: dict[str, object],
    ) -> dict[str, bytes]:
        capture = cv2.VideoCapture(segment_path)
        if not capture.isOpened():
            return {}

        payloads: dict[str, bytes] = {}
        try:
            for role, observation in observations.items():
                frame_index = int(getattr(observation, "frame_index"))
                capture.set(cv2.CAP_PROP_POS_FRAMES, max(frame_index, 0))
                ok, frame_bgr = capture.read()
                if not ok:
                    continue
                payloads[role] = self._artifact_store.encode_frame(frame_bgr)
        finally:
            capture.release()
        return payloads
