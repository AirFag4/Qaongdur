from __future__ import annotations

import json
import logging
from pathlib import Path
from threading import Lock, Thread
import time
from uuid import uuid4

import cv2

from .artifact_store import ArtifactStore
from .config import Settings
from .database import VisionRepository
from .detection import ObjectDetector
from .domain import ClosedTrack, MockVideoSource, utcnow_iso
from .embedding import CropEmbedder
from .face import FaceEmbedder
from .mock_sources import build_mock_path_name, build_mock_stream_url, discover_mock_sources, slugify
from .tracking import ByteTrackManager

LOGGER = logging.getLogger(__name__)


def _isoformat_offset(offset_ms: int) -> str:
    total_seconds = max(offset_ms, 0) / 1000.0
    hours = int(total_seconds // 3600)
    minutes = int((total_seconds % 3600) // 60)
    seconds = total_seconds % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:06.3f}"


class VisionPipelineService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._repository = VisionRepository(settings.database_path)
        self._artifact_store = ArtifactStore(
            artifacts_dir=settings.artifacts_dir,
            crop_jpeg_quality=settings.crop_jpeg_quality,
            crop_max_dimension=settings.crop_max_dimension,
        )
        self._detector = ObjectDetector(
            model_name=settings.detector_model_name,
            confidence_threshold=settings.detector_confidence_threshold,
        )
        self._embedder = CropEmbedder(
            enabled=settings.embedding_enabled,
            model_name=settings.embedding_model_name,
        )
        self._face_embedder = FaceEmbedder(
            enabled=settings.face_enabled,
            model_name=settings.face_model_name,
            minimum_track_seconds=settings.face_min_track_seconds,
            service_url=settings.face_service_url,
            request_timeout_seconds=settings.face_request_timeout_seconds,
        )
        self._job_lock = Lock()
        self._job_thread: Thread | None = None
        self.refresh_sources()

    def refresh_sources(self) -> list[dict[str, object]]:
        sources = discover_mock_sources(
            self._settings.mock_video_dir,
            default_site_id=self._settings.default_site_id,
            rtsp_base_url=self._settings.mock_video_rtsp_base_url,
            path_prefix=self._settings.mock_video_path_prefix,
            use_vms=self._settings.mock_video_use_vms,
        )
        self._repository.upsert_sources(
            [
                {
                    "id": source.id,
                    "site_id": source.site_id,
                    "camera_id": source.camera_id,
                    "camera_name": source.camera_name,
                    "file_path": source.file_path,
                    "duration_sec": source.duration_sec,
                    "frame_width": source.frame_width,
                    "frame_height": source.frame_height,
                    "source_fps": source.source_fps,
                    "updated_at": utcnow_iso(),
                }
                for source in sources
            ]
        )
        return self.list_sources()

    def list_sources(self) -> list[dict[str, object]]:
        return [
            {
                "id": row["id"],
                "siteId": row["site_id"],
                "cameraId": row["camera_id"],
                "cameraName": row["camera_name"],
                "filePath": row["file_path"],
                "pathName": self._derive_path_name(row["file_path"]),
                "streamUrl": self._derive_stream_url(row["file_path"]),
                "captureMode": "rtsp-relay" if self._settings.mock_video_use_vms else "file",
                "durationSec": row["duration_sec"],
                "frameWidth": row["frame_width"],
                "frameHeight": row["frame_height"],
                "sourceFps": row["source_fps"],
                "trackCount": row["track_count"],
            }
            for row in self._repository.list_sources()
        ]

    def get_status(self) -> dict[str, object]:
        return {
            "sampleMode": self._settings.sample_mode,
            "detector": {
                "available": self._detector.status.available,
                "modelName": self._detector.status.model_name,
                "detail": self._detector.status.detail,
            },
            "embedding": {
                "modelName": self._embedder.runtime_model_name,
            },
            "face": {
                "available": self._face_embedder.runtime_available,
                "enabled": self._settings.face_enabled,
                "mode": self._face_embedder.runtime_mode,
                "modelName": self._face_embedder.runtime_model_name,
                "detail": self._face_embedder.runtime_detail,
            },
            "latestJob": self._repository.latest_job(),
            "storage": self._repository.storage_status(self._settings.storage_limit_bytes),
        }

    def list_crop_tracks(
        self,
        *,
        source_id: str | None = None,
        label: str | None = None,
    ) -> list[dict[str, object]]:
        tracks = self._repository.list_crop_tracks(source_id=source_id, label=label)
        payload: list[dict[str, object]] = []
        for track in tracks:
            assets = track["assets"]
            payload.append(
                {
                    "id": track["id"],
                    "sourceId": track["source_id"],
                    "siteId": track["site_id"],
                    "cameraId": track["camera_id"],
                    "cameraName": track["camera_name"],
                    "label": track["label"],
                    "detectorLabel": track["detector_label"],
                    "firstSeenAt": track["first_seen_at"],
                    "middleSeenAt": track["middle_seen_at"],
                    "lastSeenAt": track["last_seen_at"],
                    "firstSeenOffsetMs": track["first_seen_offset_ms"],
                    "middleSeenOffsetMs": track["middle_seen_offset_ms"],
                    "lastSeenOffsetMs": track["last_seen_offset_ms"],
                    "firstSeenOffsetLabel": _isoformat_offset(track["first_seen_offset_ms"]),
                    "middleSeenOffsetLabel": _isoformat_offset(track["middle_seen_offset_ms"]),
                    "lastSeenOffsetLabel": _isoformat_offset(track["last_seen_offset_ms"]),
                    "frameCount": track["frame_count"],
                    "sampleFps": track["sample_fps"],
                    "maxConfidence": track["max_confidence"],
                    "avgConfidence": track["avg_confidence"],
                    "embeddingStatus": track["embedding_status"],
                    "embeddingModel": track["embedding_model"],
                    "faceStatus": track["face_status"],
                    "faceModel": track["face_model"],
                    "closedReason": track["closed_reason"],
                    "firstCropDataUrl": self._artifact_store.read_as_data_url(assets["first"]),
                    "middleCropDataUrl": self._artifact_store.read_as_data_url(assets["middle"]),
                    "lastCropDataUrl": self._artifact_store.read_as_data_url(assets["last"]),
                }
            )
        return payload

    def start_job(self, *, source_ids: list[str] | None = None) -> dict[str, object]:
        with self._job_lock:
            if self._job_thread is not None and self._job_thread.is_alive():
                latest_job = self._repository.latest_job()
                if latest_job is not None:
                    return latest_job
                raise RuntimeError("A vision job is already running.")

            sources = self._resolve_sources(source_ids)
            if not sources:
                raise RuntimeError("No mock video sources are available.")

            sample_fps = min(
                max(self._settings.sample_fps, self._settings.min_sample_fps),
                self._settings.max_sample_fps,
            )
            job_id = f"job-{uuid4().hex[:10]}"
            payload = self._repository.create_job(
                job_id=job_id,
                source_ids=[source.id for source in sources],
                sampled_fps=sample_fps,
                started_at=utcnow_iso(),
            )

            self._job_thread = Thread(
                target=self._run_job,
                kwargs={
                    "job_id": job_id,
                    "sources": sources,
                    "sample_fps": sample_fps,
                },
                daemon=True,
            )
            self._job_thread.start()
            return payload

    def _resolve_sources(self, source_ids: list[str] | None) -> list[MockVideoSource]:
        source_rows = self._repository.list_sources()
        rows = source_rows if not source_ids else [
            row for row in source_rows if row["id"] in set(source_ids)
        ]
        return [
            MockVideoSource(
                id=row["id"],
                site_id=row["site_id"],
                camera_id=row["camera_id"],
                camera_name=row["camera_name"],
                file_path=row["file_path"],
                path_name=self._derive_path_name(row["file_path"]),
                stream_url=self._derive_stream_url(row["file_path"]),
                capture_mode="rtsp-relay" if self._settings.mock_video_use_vms else "file",
                duration_sec=float(row["duration_sec"]),
                frame_width=int(row["frame_width"]),
                frame_height=int(row["frame_height"]),
                source_fps=float(row["source_fps"]),
            )
            for row in rows
        ]

    def _derive_path_name(self, file_path: str) -> str:
        stem = slugify(Path(file_path).stem)
        return build_mock_path_name(
            stem=stem,
            path_prefix=self._settings.mock_video_path_prefix,
        )

    def _derive_stream_url(self, file_path: str) -> str:
        return build_mock_stream_url(
            rtsp_base_url=self._settings.mock_video_rtsp_base_url,
            path_name=self._derive_path_name(file_path),
        )

    def _run_job(
        self,
        *,
        job_id: str,
        sources: list[MockVideoSource],
        sample_fps: float,
    ) -> None:
        try:
            deleted_paths = self._repository.delete_tracks_for_sources([source.id for source in sources])
            for relative_path in deleted_paths:
                self._artifact_store.delete_relative_path(relative_path)

            track_count = 0
            for source in sources:
                track_count += self._process_source(job_id=job_id, source=source, sample_fps=sample_fps)

            self._repository.finish_job(
                job_id=job_id,
                status="completed",
                finished_at=utcnow_iso(),
                track_count=track_count,
                detail=None,
            )
        except Exception as error:  # pragma: no cover - runtime job branch
            LOGGER.exception("Vision mock job failed")
            self._repository.finish_job(
                job_id=job_id,
                status="failed",
                finished_at=utcnow_iso(),
                track_count=0,
                detail=str(error),
            )

    def _process_source(
        self,
        *,
        job_id: str,
        source: MockVideoSource,
        sample_fps: float,
    ) -> int:
        capture_target = source.stream_url if source.capture_mode == "rtsp-relay" else source.file_path
        capture = cv2.VideoCapture(capture_target)
        if not capture.isOpened():
            raise RuntimeError(
                f"Unable to open mock video source via {source.capture_mode}: {capture_target}"
            )

        try:
            if source.capture_mode == "rtsp-relay":
                return self._process_rtsp_source(
                    job_id=job_id,
                    source=source,
                    sample_fps=sample_fps,
                    capture=capture,
                )
            return self._process_file_source(
                job_id=job_id,
                source=source,
                sample_fps=sample_fps,
                capture=capture,
            )
        finally:
            capture.release()

    def _process_file_source(
        self,
        *,
        job_id: str,
        source: MockVideoSource,
        sample_fps: float,
        capture: cv2.VideoCapture,
    ) -> int:
        source_fps = source.source_fps if source.source_fps > 0 else sample_fps
        frame_interval = max(int(round(source_fps / sample_fps)), 1)
        frame_index = -1
        processed_tracks = 0
        tracker = ByteTrackManager(
            source=source,
            activation_threshold=self._settings.tracker_activation_threshold,
            matching_threshold=self._settings.tracker_matching_threshold,
            lost_buffer_frames=self._settings.tracker_lost_buffer_frames,
            minimum_consecutive_frames=self._settings.tracker_minimum_consecutive_frames,
            max_gap_frames=self._settings.tracker_max_gap_frames,
            frame_rate=sample_fps,
        )

        while True:
            ok, frame_bgr = capture.read()
            if not ok:
                break
            frame_index += 1
            if frame_index % frame_interval != 0:
                continue

            offset_ms = int(capture.get(cv2.CAP_PROP_POS_MSEC) or 0)
            detections = self._detector.detect(frame_bgr)
            closed_tracks = tracker.update(
                frame_index=frame_index,
                offset_ms=offset_ms,
                detections=detections,
                frame_bgr=frame_bgr,
            )
            for closed_track in closed_tracks:
                self._persist_track(job_id=job_id, track=closed_track, sample_fps=sample_fps)
                processed_tracks += 1

        for closed_track in tracker.finalize():
            self._persist_track(job_id=job_id, track=closed_track, sample_fps=sample_fps)
            processed_tracks += 1

        return processed_tracks

    def _process_rtsp_source(
        self,
        *,
        job_id: str,
        source: MockVideoSource,
        sample_fps: float,
        capture: cv2.VideoCapture,
    ) -> int:
        processed_tracks = 0
        tracker = ByteTrackManager(
            source=source,
            activation_threshold=self._settings.tracker_activation_threshold,
            matching_threshold=self._settings.tracker_matching_threshold,
            lost_buffer_frames=self._settings.tracker_lost_buffer_frames,
            minimum_consecutive_frames=self._settings.tracker_minimum_consecutive_frames,
            max_gap_frames=self._settings.tracker_max_gap_frames,
            frame_rate=sample_fps,
        )
        first_frame_deadline = time.monotonic() + 15.0
        started_at: float | None = None
        last_frame_at: float | None = None
        next_sample_at = 0.0
        sample_index = -1
        duration_sec = max(source.duration_sec, 1.0)
        sample_interval_sec = 1.0 / max(sample_fps, 0.1)

        while True:
            ok, frame_bgr = capture.read()
            now = time.monotonic()

            if not ok:
                if started_at is None:
                    if now >= first_frame_deadline:
                        raise RuntimeError(
                            f"Timed out waiting for the first frame from {source.stream_url}"
                        )
                elif last_frame_at is not None and now - last_frame_at >= 10.0:
                    raise RuntimeError(
                        f"RTSP relay stalled for {source.stream_url} after "
                        f"{duration_sec:.1f}s window start."
                    )
                time.sleep(0.1)
                continue

            if started_at is None:
                started_at = now
                next_sample_at = 0.0

            last_frame_at = now
            elapsed_sec = now - started_at
            if elapsed_sec >= duration_sec:
                break
            if elapsed_sec + 1e-6 < next_sample_at:
                continue

            next_sample_at += sample_interval_sec
            sample_index += 1
            offset_ms = int(min(elapsed_sec, duration_sec) * 1000)
            detections = self._detector.detect(frame_bgr)
            closed_tracks = tracker.update(
                frame_index=sample_index,
                offset_ms=offset_ms,
                detections=detections,
                frame_bgr=frame_bgr,
            )
            for closed_track in closed_tracks:
                self._persist_track(job_id=job_id, track=closed_track, sample_fps=sample_fps)
                processed_tracks += 1

        for closed_track in tracker.finalize():
            self._persist_track(job_id=job_id, track=closed_track, sample_fps=sample_fps)
            processed_tracks += 1

        return processed_tracks

    def _persist_track(
        self,
        *,
        job_id: str,
        track: ClosedTrack,
        sample_fps: float,
    ) -> None:
        first_observation = track.first_observation()
        middle_observation = track.middle_observation()
        last_observation = track.last_observation()
        crop_payloads = {
            "first": self._artifact_store.encode_crop(first_observation.crop_bgr),
            "middle": self._artifact_store.encode_crop(middle_observation.crop_bgr),
            "last": self._artifact_store.encode_crop(last_observation.crop_bgr),
        }
        required_bytes = sum(len(payload) for payload in crop_payloads.values())
        deleted_paths = self._repository.prune_oldest_tracks_until_fit(
            storage_limit_bytes=self._settings.storage_limit_bytes,
            bytes_needed=required_bytes,
        )
        for relative_path in deleted_paths:
            self._artifact_store.delete_relative_path(relative_path)

        artifacts: list[dict[str, object]] = []
        for role, payload in crop_payloads.items():
            relative_path = self._artifact_store.write_bytes(
                f"tracks/{track.id}/{role}.jpg",
                payload,
            )
            artifacts.append(
                {
                    "id": f"asset-{uuid4().hex[:10]}",
                    "track_id": track.id,
                    "source_id": track.source.id,
                    "role": role,
                    "kind": "crop",
                    "relative_path": relative_path,
                    "mime_type": "image/jpeg",
                    "byte_size": len(payload),
                    "created_at": utcnow_iso(),
                }
            )

        embedding = self._embedder.embed(middle_observation.crop_bgr)
        face_embedding = self._face_embedder.maybe_embed(
            label=track.label,
            duration_seconds=track.duration_seconds,
            crop_bgr=middle_observation.crop_bgr,
        )

        self._repository.insert_track(
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
                "frame_count": track.frame_count,
                "sample_fps": sample_fps,
                "max_confidence": track.max_confidence,
                "avg_confidence": track.avg_confidence,
                "first_bbox_json": json.dumps(first_observation.bbox),
                "middle_bbox_json": json.dumps(middle_observation.bbox),
                "last_bbox_json": json.dumps(last_observation.bbox),
                "embedding_status": embedding.status,
                "embedding_model": embedding.model_name,
                "embedding_dim": len(embedding.vector),
                "face_status": face_embedding.status,
                "face_model": face_embedding.model_name,
                "face_dim": len(face_embedding.vector) if face_embedding.vector else None,
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
