from __future__ import annotations

import base64
import binascii
import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from itertools import count
from pathlib import Path
from queue import Empty, PriorityQueue
from threading import Event, Lock, Thread
import time
from uuid import uuid4

import cv2
import numpy as np

from .artifact_store import ArtifactStore
from .config import Settings
from .control_api import ControlApiError, SourceCatalogClient
from .database import VisionRepository
from .detection import ObjectDetector
from .domain import ClosedTrack, VisionSource, utcnow_iso
from .embedding import CropEmbedder
from .face import FaceEmbedder
from .tracking import ByteTrackManager
from .vector_store import QdrantVectorStore

LOGGER = logging.getLogger(__name__)


def _isoformat_offset(offset_ms: int) -> str:
    total_seconds = max(offset_ms, 0) / 1000.0
    hours = int(total_seconds // 3600)
    minutes = int((total_seconds % 3600) // 60)
    seconds = total_seconds % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:06.3f}"


def _parse_segment_start(segment_path: Path) -> datetime | None:
    try:
        return datetime.strptime(segment_path.stem, "%Y-%m-%d_%H-%M-%S-%f").replace(tzinfo=UTC)
    except ValueError:
        return None


def _point_from_bbox(bbox: tuple[int, int, int, int]) -> dict[str, int]:
    x1, y1, x2, y2 = bbox
    return {
        "x": int((x1 + x2) / 2),
        "y": int((y1 + y2) / 2),
    }


@dataclass(slots=True)
class SegmentTask:
    source: VisionSource
    segment_path: str
    segment_start_at: str
    byte_size: int


class VisionPipelineService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._repository = VisionRepository(settings.database_path)
        self._artifact_store = ArtifactStore(
            artifacts_dir=settings.artifacts_dir,
            crop_jpeg_quality=settings.crop_jpeg_quality,
            crop_max_dimension=settings.crop_max_dimension,
            frame_max_dimension=settings.frame_max_dimension,
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
        self._vector_store = QdrantVectorStore(
            enabled=settings.vector_store_enabled,
            base_url=settings.vector_store_url,
            object_collection=settings.vector_store_object_collection,
            face_collection=settings.vector_store_face_collection,
            timeout_seconds=settings.vector_store_timeout_seconds,
        )
        self._source_client = SourceCatalogClient(
            base_url=settings.control_api_url,
            internal_token=settings.internal_service_token,
        )
        self._task_queue: PriorityQueue[tuple[float, int, SegmentTask]] = PriorityQueue()
        self._task_sequence = count()
        self._wake_scanner = Event()
        self._job_lock = Lock()
        self._detector_lock = Lock()
        self._embedding_lock = Lock()
        self._vector_store_lock = Lock()
        self._latest_source_sync_at: str | None = None
        self._latest_source_sync_error: str | None = None
        self._worker_threads = [
            Thread(
                target=self._worker_loop,
                daemon=True,
                name=f"vision-worker-{index + 1}",
            )
            for index in range(max(self._settings.segment_worker_count, 1))
        ]
        self._scanner_thread = Thread(target=self._scanner_loop, daemon=True, name="vision-scanner")
        try:
            self.refresh_sources()
        except Exception as error:  # pragma: no cover - startup dependency path
            self._latest_source_sync_error = str(error)
            LOGGER.warning("Initial vision source sync failed: %s", error)
        for worker_thread in self._worker_threads:
            worker_thread.start()
        self._scanner_thread.start()

    def refresh_sources(self, *, include_retired: bool = False) -> list[dict[str, object]]:
        sources = self._source_client.list_sources()
        self._repository.sync_sources(
            [
                {
                    "id": source.id,
                    "site_id": source.site_id,
                    "camera_id": source.camera_id,
                    "camera_name": source.camera_name,
                    "path_name": source.path_name,
                    "stream_url": source.stream_url,
                    "live_stream_url": source.live_stream_url,
                    "health": source.health,
                    "source_kind": source.source_kind,
                    "ingest_mode": source.ingest_mode,
                    "file_path": source.file_path,
                    "duration_sec": source.duration_sec,
                    "frame_width": source.frame_width,
                    "frame_height": source.frame_height,
                    "source_fps": source.source_fps,
                    "updated_at": utcnow_iso(),
                    "last_segment_at": None,
                    "retired_at": None,
                }
                for source in sources
            ]
        )
        if self._settings.purge_retired_mock_history:
            deleted_paths = self._repository.purge_retired_sources(source_kind="mock-video")
            for relative_path in deleted_paths:
                self._artifact_store.delete_relative_path(relative_path)
        self._latest_source_sync_at = utcnow_iso()
        self._latest_source_sync_error = None
        return self.list_sources(include_retired=include_retired)

    def list_sources(self, *, include_retired: bool = False) -> list[dict[str, object]]:
        return [
            {
                "id": row["id"],
                "siteId": row["site_id"],
                "cameraId": row["camera_id"],
                "cameraName": row["camera_name"],
                "pathName": row["path_name"],
                "relayRtspUrl": row["stream_url"],
                "liveStreamUrl": row["live_stream_url"],
                "sourceKind": row["source_kind"],
                "ingestMode": row["ingest_mode"],
                "health": row["health"],
                "trackCount": row["track_count"],
                "processedSegmentCount": row["processed_segment_count"],
                "latestProcessedAt": row["latest_processed_at"],
                "lastSegmentAt": row["last_segment_at"],
                "retiredAt": row.get("retired_at"),
            }
            for row in self._repository.list_sources(include_retired=include_retired)
        ]

    def get_status(self) -> dict[str, object]:
        return {
            "sampleMode": self._settings.sample_mode,
            "autoIngest": True,
            "detector": {
                "available": self._detector.status.available,
                "modelName": self._detector.status.model_name,
                "detail": self._detector.status.detail,
            },
            "embedding": {
                "enabled": self._settings.embedding_enabled,
                "state": self._embedder.runtime_state,
                "modelName": self._embedder.runtime_model_name,
                "detail": self._embedder.runtime_detail,
            },
            "face": {
                "available": self._face_embedder.runtime_available,
                "enabled": self._settings.face_enabled,
                "mode": self._face_embedder.runtime_mode,
                "modelName": self._face_embedder.runtime_model_name,
                "detail": self._face_embedder.runtime_detail,
            },
            "vectorStore": {
                "enabled": self._vector_store.status.enabled,
                "available": self._vector_store.status.available,
                "provider": self._vector_store.status.provider,
                "detail": self._vector_store.status.detail,
            },
            "latestJob": self._repository.latest_job(),
            "storage": self._repository.storage_status(self._settings.effective_storage_limit_bytes),
            "sourceSync": {
                "lastSyncedAt": self._latest_source_sync_at,
                "error": self._latest_source_sync_error,
            },
            "queueDepth": self._task_queue.qsize(),
            "segmentWorkerCount": max(self._settings.segment_worker_count, 1),
            "sampleFps": min(
                max(self._settings.sample_fps, self._settings.min_sample_fps),
                self._settings.max_sample_fps,
            ),
        }

    def list_crop_tracks(
        self,
        *,
        source_id: str | None = None,
        camera_id: str | None = None,
        label: str | None = None,
        from_at: str | None = None,
        to_at: str | None = None,
        include_retired: bool = False,
        page: int = 1,
        page_size: int = 20,
    ) -> dict[str, object]:
        result = self._repository.list_crop_tracks(
            source_id=source_id,
            camera_id=camera_id,
            label=label,
            from_at=from_at,
            to_at=to_at,
            include_retired=include_retired,
            page=page,
            page_size=page_size,
        )
        return {
            **result,
            "tracks": [self._serialize_track(track) for track in result["tracks"]],
        }

    def get_crop_track(self, track_id: str) -> dict[str, object] | None:
        track = self._repository.get_crop_track(track_id)
        if track is None:
            return None
        return self._serialize_track(track, include_detail=True)

    def search_crop_tracks(
        self,
        *,
        text_query: str | None = None,
        image_base64: str | None = None,
        source_id: str | None = None,
        camera_id: str | None = None,
        label: str | None = None,
        from_at: str | None = None,
        to_at: str | None = None,
        include_retired: bool = False,
        page: int = 1,
        page_size: int = 20,
    ) -> dict[str, object]:
        normalized_text = (text_query or "").strip()
        normalized_image = (image_base64 or "").strip()
        if not normalized_text and not normalized_image:
            return self.list_crop_tracks(
                source_id=source_id,
                camera_id=camera_id,
                label=label,
                from_at=from_at,
                to_at=to_at,
                include_retired=include_retired,
                page=page,
                page_size=page_size,
            )

        ranked_matches: list[dict[str, object]] = []
        executed_search_modes: list[str] = []
        image_query_debug: dict[str, object] | None = None
        if normalized_image:
            image_bgr = self._decode_query_image(normalized_image)
            face_result = self._face_embedder.embed_query_image(image_bgr)
            image_query_debug = self._serialize_image_query_debug(face_result)
            if face_result.status == "ready" and face_result.vector:
                executed_search_modes.append("face-image")
                ranked_matches.extend(
                    self._search_tracks_by_vector(
                        vector=face_result.vector,
                        model_name=face_result.model_name,
                        embedding_kind="face",
                        reason="face-image",
                        source_id=source_id,
                        camera_id=camera_id,
                        label=label,
                        from_at=from_at,
                        to_at=to_at,
                        include_retired=include_retired,
                    )
                )
            else:
                with self._embedding_lock:
                    image_embedding = self._embedder.embed(image_bgr)
                if image_embedding.vector:
                    executed_search_modes.append("image")
                    ranked_matches.extend(
                        self._search_tracks_by_vector(
                            vector=image_embedding.vector,
                            model_name=image_embedding.model_name,
                            embedding_kind="object",
                            reason="image",
                            source_id=source_id,
                            camera_id=camera_id,
                            label=label,
                            from_at=from_at,
                            to_at=to_at,
                            include_retired=include_retired,
                        )
                    )

        if normalized_text:
            with self._embedding_lock:
                text_embedding = self._embedder.embed_text(normalized_text)
            if text_embedding.vector:
                executed_search_modes.append("text")
                ranked_matches.extend(
                    self._search_tracks_by_vector(
                        vector=text_embedding.vector,
                        model_name=text_embedding.model_name,
                        embedding_kind="object",
                        reason="text",
                        source_id=source_id,
                        camera_id=camera_id,
                        label=label,
                        from_at=from_at,
                        to_at=to_at,
                        include_retired=include_retired,
                    )
                )
            else:
                executed_search_modes.append("text-fallback")
                ranked_matches.extend(
                    self._search_tracks_by_text_fallback(
                        text_query=normalized_text,
                        source_id=source_id,
                        camera_id=camera_id,
                        label=label,
                        from_at=from_at,
                        to_at=to_at,
                        include_retired=include_retired,
                    )
                )

        merged_matches = self._merge_ranked_matches(ranked_matches)
        page_size = max(page_size, 1)
        page = max(page, 1)
        total_count = len(merged_matches)
        total_pages = max((total_count + page_size - 1) // page_size, 1)
        safe_page = min(page, total_pages)
        start_index = (safe_page - 1) * page_size
        selected_matches = merged_matches[start_index : start_index + page_size]
        tracks = self._repository.get_crop_tracks_by_ids(
            [str(match["trackId"]) for match in selected_matches]
        )
        match_by_id = {str(match["trackId"]): match for match in selected_matches}
        track_by_id = {str(track["id"]): track for track in tracks}
        serialized = [
            self._serialize_track(
                {
                    **track_by_id[track_id],
                    "search_score": match_by_id[track_id]["score"],
                    "search_reason": match_by_id[track_id]["reason"],
                }
            )
            for track_id in [str(match["trackId"]) for match in selected_matches]
            if track_id in track_by_id
        ]
        return {
            "tracks": serialized,
            "totalCount": total_count,
            "page": safe_page,
            "pageSize": page_size,
            "totalPages": total_pages,
            "searchModes": executed_search_modes,
            "imageQueryDebug": image_query_debug,
        }

    def start_job(self, *, source_ids: list[str] | None = None) -> dict[str, object]:
        del source_ids
        self._wake_scanner.set()
        latest_job = self._repository.latest_job()
        if latest_job is not None:
            return latest_job
        sample_fps = min(
            max(self._settings.sample_fps, self._settings.min_sample_fps),
            self._settings.max_sample_fps,
        )
        return {
            "id": f"scan-{uuid4().hex[:10]}",
            "status": "running",
            "sourceIds": [],
            "sampledFps": sample_fps,
            "trackCount": 0,
            "startedAt": utcnow_iso(),
            "detail": "Requested an immediate recordings scan.",
        }

    def _serialize_track(
        self,
        track: dict[str, object],
        *,
        include_detail: bool = False,
    ) -> dict[str, object]:
        assets = track["assets"]
        payload: dict[str, object] = {
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
            "firstSeenOffsetLabel": _isoformat_offset(int(track["first_seen_offset_ms"])),
            "middleSeenOffsetLabel": _isoformat_offset(int(track["middle_seen_offset_ms"])),
            "lastSeenOffsetLabel": _isoformat_offset(int(track["last_seen_offset_ms"])),
            "segmentPath": track.get("segment_path"),
            "segmentStartAt": track.get("segment_start_at"),
            "segmentDurationSec": track.get("segment_duration_sec"),
            "frameCount": track["frame_count"],
            "sampleFps": track["sample_fps"],
            "maxConfidence": track["max_confidence"],
            "avgConfidence": track["avg_confidence"],
            "embeddingStatus": track["embedding_status"],
            "embeddingModel": track["embedding_model"],
            "embeddingDim": track.get("embedding_dim") or track.get("embedding_vector_dim"),
            "faceStatus": track["face_status"],
            "faceModel": track["face_model"],
            "faceDim": track.get("face_dim") or track.get("face_vector_dim"),
            "faceCount": track.get("face_count") or 0,
            "faceDetail": track.get("face_detail"),
            "closedReason": track["closed_reason"],
            "firstPoint": json.loads(track["first_point_json"]) if track.get("first_point_json") else None,
            "middlePoint": json.loads(track["middle_point_json"]) if track.get("middle_point_json") else None,
            "lastPoint": json.loads(track["last_point_json"]) if track.get("last_point_json") else None,
            "middleCropDataUrl": self._artifact_store.read_as_data_url(assets.get("middle")),
            "searchScore": track.get("search_score"),
            "searchReason": track.get("search_reason"),
        }
        if include_detail:
            payload.update(
                {
                    "firstCropDataUrl": self._artifact_store.read_as_data_url(assets.get("first")),
                    "lastCropDataUrl": self._artifact_store.read_as_data_url(assets.get("last")),
                    "firstBBox": json.loads(track["first_bbox_json"]),
                    "middleBBox": json.loads(track["middle_bbox_json"]),
                    "lastBBox": json.loads(track["last_bbox_json"]),
                    "sourceFrameWidth": track.get("source_frame_width"),
                    "sourceFrameHeight": track.get("source_frame_height"),
                    "firstFrameDataUrl": (
                        self._artifact_store.read_as_data_url(assets["frame-first"])
                        if assets.get("frame-first")
                        else None
                    ),
                    "middleFrameDataUrl": (
                        self._artifact_store.read_as_data_url(assets["frame-middle"])
                        if assets.get("frame-middle")
                        else None
                    ),
                    "lastFrameDataUrl": (
                        self._artifact_store.read_as_data_url(assets["frame-last"])
                        if assets.get("frame-last")
                        else None
                    ),
                    "faceDetectedDataUrl": (
                        self._artifact_store.read_as_data_url(assets["face-detected"])
                        if assets.get("face-detected")
                        else None
                    ),
                    "faceAlignedDataUrl": (
                        self._artifact_store.read_as_data_url(assets["face-aligned"])
                        if assets.get("face-aligned")
                        else None
                    ),
                    "createdAt": track["created_at"],
                }
            )
        return payload

    def _decode_query_image(self, image_base64: str) -> np.ndarray:
        encoded = image_base64.strip()
        if "," in encoded and encoded.lower().startswith("data:"):
            encoded = encoded.split(",", 1)[1]
        try:
            image_bytes = base64.b64decode(encoded)
        except (ValueError, binascii.Error) as error:
            raise ValueError(f"Invalid base64 image payload: {error}") from error

        image_array = np.frombuffer(image_bytes, dtype=np.uint8)
        image_bgr = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
        if image_bgr is None:
            raise ValueError("Unable to decode the uploaded image.")
        return image_bgr

    def _serialize_image_query_debug(
        self,
        result: FaceEmbeddingResult,
    ) -> dict[str, object]:
        return {
            "faceStatus": result.status,
            "faceCount": result.face_count,
            "detail": result.detail,
            "faceBBox": list(result.face_bbox) if result.face_bbox else None,
            "detectedFaceDataUrl": (
                self._artifact_store.data_url_for_bytes(result.detected_face_jpeg)
                if result.detected_face_jpeg
                else None
            ),
            "alignedFaceDataUrl": (
                self._artifact_store.data_url_for_bytes(result.aligned_face_jpeg)
                if result.aligned_face_jpeg
                else None
            ),
        }

    def _search_tracks_by_vector(
        self,
        *,
        vector: list[float],
        model_name: str,
        embedding_kind: str,
        reason: str,
        source_id: str | None,
        camera_id: str | None,
        label: str | None,
        from_at: str | None,
        to_at: str | None,
        include_retired: bool,
    ) -> list[dict[str, object]]:
        query = np.asarray(vector, dtype=np.float32)
        query_norm = float(np.linalg.norm(query))
        if query_norm <= 0:
            return []
        query = query / query_norm

        candidate_rows = self._repository.list_crop_track_candidates(
            source_id=source_id,
            camera_id=camera_id,
            label=label,
            from_at=from_at,
            to_at=to_at,
            include_retired=include_retired,
        )
        if not candidate_rows:
            return []

        last_seen_by_track_id = {
            str(candidate["id"]): str(candidate["last_seen_at"])
            for candidate in candidate_rows
        }
        with self._vector_store_lock:
            ranked_from_vector_store = self._vector_store.search_embeddings(
                embedding_kind=embedding_kind,
                vector=query.astype(float).tolist(),
                track_ids=list(last_seen_by_track_id),
            )
        if ranked_from_vector_store is not None:
            return [
                {
                    "trackId": str(match["trackId"]),
                    "score": float(match["score"]),
                    "reason": reason,
                    "reasonCount": 1,
                    "lastSeenAt": last_seen_by_track_id.get(
                        str(match["trackId"]),
                        "",
                    ),
                }
                for match in ranked_from_vector_store
                if str(match["trackId"]) in last_seen_by_track_id
            ]

        candidates = self._repository.search_vector_candidates(
            embedding_kind=embedding_kind,
            model_name=model_name,
            source_id=source_id,
            camera_id=camera_id,
            label=label,
            from_at=from_at,
            to_at=to_at,
            include_retired=include_retired,
        )
        ranked: list[dict[str, object]] = []
        for candidate in candidates:
            try:
                candidate_vector = np.asarray(
                    json.loads(str(candidate["vector_json"])),
                    dtype=np.float32,
                )
            except (TypeError, ValueError, json.JSONDecodeError):
                continue
            if candidate_vector.shape != query.shape:
                continue
            candidate_norm = float(np.linalg.norm(candidate_vector))
            if candidate_norm <= 0:
                continue
            similarity = float(np.dot(query, candidate_vector / candidate_norm))
            if similarity <= 0:
                continue
            ranked.append(
                {
                    "trackId": str(candidate["id"]),
                    "score": round(similarity, 6),
                    "reason": reason,
                    "reasonCount": 1,
                    "lastSeenAt": str(candidate["last_seen_at"]),
                }
            )
        ranked.sort(
            key=lambda item: (
                float(item["score"]),
                int(item.get("reasonCount", 1)),
                str(item["lastSeenAt"]),
            ),
            reverse=True,
        )
        return ranked

    def _merge_ranked_matches(
        self,
        ranked_matches: list[dict[str, object]],
    ) -> list[dict[str, object]]:
        merged: list[dict[str, object]] = []
        seen: dict[str, int] = {}
        for match in ranked_matches:
            track_id = str(match["trackId"])
            if track_id in seen:
                existing = merged[seen[track_id]]
                existing_reasons = set(str(existing["reason"]).split("+"))
                existing_reasons.add(str(match["reason"]))
                existing["reason"] = "+".join(sorted(existing_reasons))
                existing["reasonCount"] = len(existing_reasons)
                existing["score"] = max(float(existing["score"]), float(match["score"]))
                existing["lastSeenAt"] = max(
                    str(existing["lastSeenAt"]),
                    str(match["lastSeenAt"]),
                )
                continue
            seen[track_id] = len(merged)
            entry = dict(match)
            entry["reasonCount"] = int(entry.get("reasonCount", 1))
            merged.append(entry)

        merged.sort(
            key=lambda item: (
                float(item["score"]),
                int(item.get("reasonCount", 1)),
                str(item["lastSeenAt"]),
            ),
            reverse=True,
        )
        return merged

    def _search_tracks_by_text_fallback(
        self,
        *,
        text_query: str,
        source_id: str | None,
        camera_id: str | None,
        label: str | None,
        from_at: str | None,
        to_at: str | None,
        include_retired: bool,
    ) -> list[dict[str, object]]:
        tokens = [
            token
            for token in "".join(
                character if character.isalnum() else " "
                for character in text_query.lower()
            ).split()
            if len(token) >= 2
        ]
        if not tokens:
            return []

        candidates = self._repository.search_text_candidates(
            source_id=source_id,
            camera_id=camera_id,
            label=label,
            from_at=from_at,
            to_at=to_at,
            include_retired=include_retired,
        )
        ranked: list[dict[str, object]] = []
        joined_query = " ".join(tokens)
        for candidate in candidates:
            haystack = " ".join(
                [
                    str(candidate.get("camera_name", "")).lower(),
                    str(candidate.get("label", "")).lower(),
                    str(candidate.get("detector_label", "")).lower(),
                ]
            )
            token_hits = sum(1 for token in tokens if token in haystack)
            if token_hits == 0:
                continue
            phrase_bonus = 1 if joined_query and joined_query in haystack else 0
            score = min(
                (token_hits + phrase_bonus) / max(len(tokens) + 1, 1),
                1.0,
            )
            ranked.append(
                {
                    "trackId": str(candidate["id"]),
                    "score": round(float(score), 6),
                    "reason": "text-fallback",
                    "reasonCount": 1,
                    "lastSeenAt": str(candidate["last_seen_at"]),
                }
            )
        ranked.sort(
            key=lambda item: (
                float(item["score"]),
                int(item.get("reasonCount", 1)),
                str(item["lastSeenAt"]),
            ),
            reverse=True,
        )
        return ranked

    def _scanner_loop(self) -> None:
        while True:
            try:
                self.refresh_sources()
                self._scan_recording_segments()
            except ControlApiError as error:  # pragma: no cover - runtime integration path
                self._latest_source_sync_error = str(error)
                LOGGER.warning("Unable to refresh live vision sources: %s", error)
            except Exception:  # pragma: no cover - runtime integration path
                LOGGER.exception("Vision recordings scan failed")

            self._wake_scanner.wait(self._settings.segment_poll_interval_seconds)
            self._wake_scanner.clear()

    def _scan_recording_segments(self) -> None:
        recordings_root = Path(self._settings.recordings_dir)
        if not recordings_root.exists():
            return

        sources_by_path = {
            str(row["path_name"]): VisionSource(
                id=str(row["id"]),
                site_id=str(row["site_id"]),
                camera_id=str(row["camera_id"]),
                camera_name=str(row["camera_name"]),
                path_name=str(row["path_name"]),
                stream_url=str(row["stream_url"]),
                live_stream_url=(str(row["live_stream_url"]) if row.get("live_stream_url") else None),
                capture_mode="recording-segment",
                source_kind=str(row["source_kind"]),
                ingest_mode=str(row["ingest_mode"]),
                health=str(row["health"]),
                file_path=str(row["file_path"]),
                duration_sec=float(row["duration_sec"]),
                frame_width=int(row["frame_width"]),
                frame_height=int(row["frame_height"]),
                source_fps=float(row["source_fps"]),
            )
            for row in self._repository.list_sources(include_retired=False)
        }

        now = time.time()
        segment_paths = sorted(
            recordings_root.rglob("*.mp4"),
            key=lambda candidate: candidate.stat().st_mtime,
            reverse=True,
        )
        for segment_path in segment_paths:
            try:
                relative_path = segment_path.relative_to(recordings_root)
            except ValueError:
                continue
            if len(relative_path.parts) < 2:
                continue
            if now - segment_path.stat().st_mtime < self._settings.segment_min_age_seconds:
                continue

            path_name = relative_path.parts[0]
            source = sources_by_path.get(path_name)
            if source is None:
                continue

            segment_start_at = _parse_segment_start(segment_path)
            if segment_start_at is None:
                continue

            is_new = self._repository.register_segment(
                segment_path=str(segment_path),
                source_id=source.id,
                path_name=source.path_name,
                camera_id=source.camera_id,
                camera_name=source.camera_name,
                segment_start_at=segment_start_at.isoformat(),
                byte_size=segment_path.stat().st_size,
                created_at=utcnow_iso(),
            )
            if not is_new:
                continue

            self._enqueue_segment_task(
                SegmentTask(
                    source=source,
                    segment_path=str(segment_path),
                    segment_start_at=segment_start_at.isoformat(),
                    byte_size=segment_path.stat().st_size,
                ),
            )

    def _worker_loop(self) -> None:
        while True:
            try:
                _, _, task = self._task_queue.get(timeout=1.0)
            except Empty:
                continue

            try:
                self._process_segment(task)
            except Exception:  # pragma: no cover - runtime integration path
                LOGGER.exception("Vision segment processing failed for %s", task.segment_path)
            finally:
                self._task_queue.task_done()

    def _enqueue_segment_task(self, task: SegmentTask) -> None:
        try:
            priority = -datetime.fromisoformat(task.segment_start_at.replace("Z", "+00:00")).timestamp()
        except ValueError:
            priority = 0.0
        self._task_queue.put((priority, next(self._task_sequence), task))

    def _process_segment(self, task: SegmentTask) -> None:
        sample_fps = min(
            max(self._settings.sample_fps, self._settings.min_sample_fps),
            self._settings.max_sample_fps,
        )
        job_id = f"job-{uuid4().hex[:10]}"
        self._repository.create_job(
            job_id=job_id,
            source_ids=[task.source.id],
            sampled_fps=sample_fps,
            started_at=utcnow_iso(),
        )
        self._repository.mark_segment_processing(segment_path=task.segment_path, job_id=job_id)

        try:
            track_count, duration_sec = self._process_segment_file(
                job_id=job_id,
                source=task.source,
                sample_fps=sample_fps,
                segment_path=task.segment_path,
                segment_start_at=task.segment_start_at,
            )
        except Exception as error:
            self._repository.finish_job(
                job_id=job_id,
                status="failed",
                finished_at=utcnow_iso(),
                track_count=0,
                detail=str(error),
            )
            self._repository.mark_segment_failed(
                segment_path=task.segment_path,
                processed_at=utcnow_iso(),
                detail=str(error),
            )
            raise

        finished_at = utcnow_iso()
        segment_end_at = (
            datetime.fromisoformat(task.segment_start_at.replace("Z", "+00:00"))
            + timedelta(seconds=duration_sec)
        ).astimezone(UTC).isoformat()
        self._repository.finish_job(
            job_id=job_id,
            status="completed",
            finished_at=finished_at,
            track_count=track_count,
            detail=f"Processed recording chunk {Path(task.segment_path).name}",
        )
        self._repository.mark_segment_processed(
            segment_path=task.segment_path,
            processed_at=finished_at,
            duration_sec=duration_sec,
            segment_end_at=segment_end_at,
            track_count=track_count,
        )

    def _process_segment_file(
        self,
        *,
        job_id: str,
        source: VisionSource,
        sample_fps: float,
        segment_path: str,
        segment_start_at: str,
    ) -> tuple[int, float]:
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
            frame_interval = max(int(round(capture_fps / sample_fps)), 1)
            segment_start_dt = datetime.fromisoformat(segment_start_at.replace("Z", "+00:00"))
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

            frame_index = -1
            last_offset_ms = 0
            while True:
                ok, frame_bgr = capture.read()
                if not ok:
                    break
                frame_index += 1
                if frame_index % frame_interval != 0:
                    continue

                offset_ms = int(capture.get(cv2.CAP_PROP_POS_MSEC) or 0)
                if offset_ms <= 0 and capture_fps > 0:
                    offset_ms = int((frame_index / capture_fps) * 1000)
                last_offset_ms = max(last_offset_ms, offset_ms)
                captured_at = (segment_start_dt + timedelta(milliseconds=offset_ms)).astimezone(UTC).isoformat()
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
                    self._persist_track(
                        job_id=job_id,
                        track=closed_track,
                        sample_fps=sample_fps,
                        segment_path=segment_path,
                        segment_start_at=segment_start_at,
                        segment_duration_sec=max(estimated_duration_sec, last_offset_ms / 1000.0),
                    )
                    processed_tracks += 1

            final_duration_sec = max(estimated_duration_sec, last_offset_ms / 1000.0)
            for closed_track in tracker.finalize():
                self._persist_track(
                    job_id=job_id,
                    track=closed_track,
                    sample_fps=sample_fps,
                    segment_path=segment_path,
                    segment_start_at=segment_start_at,
                    segment_duration_sec=final_duration_sec,
                )
                processed_tracks += 1

            return processed_tracks, final_duration_sec
        finally:
            capture.release()

    def _persist_track(
        self,
        *,
        job_id: str,
        track: ClosedTrack,
        sample_fps: float,
        segment_path: str,
        segment_start_at: str,
        segment_duration_sec: float,
    ) -> None:
        first_observation = track.first_observation()
        middle_observation = track.middle_observation()
        last_observation = track.last_observation()
        with self._embedding_lock:
            embedding = self._embedder.embed(middle_observation.crop_bgr)
        face_embedding = self._face_embedder.maybe_embed(
            label=track.label,
            duration_seconds=track.duration_seconds,
            crop_bgr=middle_observation.crop_bgr,
        )

        crop_payloads = {
            "first": self._artifact_store.encode_crop(first_observation.crop_bgr),
            "middle": self._artifact_store.encode_crop(middle_observation.crop_bgr),
            "last": self._artifact_store.encode_crop(last_observation.crop_bgr),
        }
        frame_payloads = self._encode_observation_frames(
            segment_path=segment_path,
            observations={
                "frame-first": first_observation,
                "frame-middle": middle_observation,
                "frame-last": last_observation,
            },
        )
        face_payloads = {
            role: payload
            for role, payload in {
                "face-detected": face_embedding.detected_face_jpeg,
                "face-aligned": face_embedding.aligned_face_jpeg,
            }.items()
            if payload
        }
        required_bytes = (
            sum(len(payload) for payload in crop_payloads.values())
            + sum(len(payload) for payload in frame_payloads.values())
            + sum(len(payload) for payload in face_payloads.values())
        )
        deleted_paths = self._repository.prune_oldest_tracks_until_fit(
            storage_limit_bytes=self._settings.effective_storage_limit_bytes,
            bytes_needed=required_bytes,
        )
        for relative_path in deleted_paths:
            self._artifact_store.delete_relative_path(relative_path)

        artifacts: list[dict[str, object]] = []
        for role, payload in {**crop_payloads, **frame_payloads, **face_payloads}.items():
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
                    "kind": (
                        "frame"
                        if role.startswith("frame-")
                        else "face"
                        if role.startswith("face-")
                        else "crop"
                    ),
                    "relative_path": relative_path,
                    "mime_type": "image/jpeg",
                    "byte_size": len(payload),
                    "created_at": utcnow_iso(),
                }
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
