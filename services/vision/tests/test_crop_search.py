from __future__ import annotations

import base64
import json
from threading import Lock

import cv2
import numpy as np

from vision_service.database import VisionRepository
from vision_service.embedding import EmbeddingResult
from vision_service.face import FaceEmbeddingResult
from vision_service.pipeline import VisionPipelineService


class _ArtifactStoreStub:
    def read_as_data_url(self, path: str | None) -> str | None:
        del path
        return None


class _ObjectEmbedderStub:
    def __init__(
        self,
        *,
        text_vector: list[float] | None = None,
        image_vector: list[float] | None = None,
    ) -> None:
        self._text_vector = text_vector or []
        self._image_vector = image_vector or []
        self.image_calls = 0

    def embed_text(self, text: str) -> EmbeddingResult:
        del text
        return EmbeddingResult(
            status="ready" if self._text_vector else "text-unsupported",
            model_name="test-object-model",
            vector=self._text_vector,
        )

    def embed(self, crop_bgr: np.ndarray) -> EmbeddingResult:
        del crop_bgr
        self.image_calls += 1
        return EmbeddingResult(
            status="ready" if self._image_vector else "fallback",
            model_name="test-object-model",
            vector=self._image_vector,
        )


class _FaceEmbedderStub:
    def __init__(
        self,
        *,
        status: str = "service-not-ready",
        vector: list[float] | None = None,
    ) -> None:
        self._status = status
        self._vector = vector
        self.calls = 0

    def embed_query_image(self, image_bgr: np.ndarray) -> FaceEmbeddingResult:
        del image_bgr
        self.calls += 1
        return FaceEmbeddingResult(
            status=self._status,
            model_name="test-face-model",
            vector=self._vector,
            detail=None,
            face_count=1 if self._vector else 0,
        )


def _service_with_repository(
    repository: VisionRepository,
    *,
    object_embedder: _ObjectEmbedderStub,
    face_embedder: _FaceEmbedderStub,
) -> VisionPipelineService:
    service = VisionPipelineService.__new__(VisionPipelineService)
    service._repository = repository
    service._artifact_store = _ArtifactStoreStub()
    service._embedder = object_embedder
    service._face_embedder = face_embedder
    service._embedding_lock = Lock()
    return service


def _source_row(source_id: str, *, updated_at: str) -> dict[str, object]:
    return {
        "id": source_id,
        "site_id": "site-local-01",
        "camera_id": f"cam-{source_id}",
        "camera_name": f"Camera {source_id}",
        "path_name": f"path-{source_id}",
        "stream_url": f"rtsp://mediamtx:8554/path-{source_id}",
        "live_stream_url": None,
        "health": "healthy",
        "source_kind": "mock-video",
        "ingest_mode": "publish",
        "file_path": f"/mock-videos/{source_id}.mp4",
        "duration_sec": 60.0,
        "frame_width": 1280,
        "frame_height": 720,
        "source_fps": 15.0,
        "updated_at": updated_at,
        "last_segment_at": None,
        "retired_at": None,
    }


def _insert_track(
    repository: VisionRepository,
    *,
    track_id: str,
    label: str,
    detector_label: str,
    first_seen_at: str,
    last_seen_at: str,
    object_vector: list[float] | None = None,
    face_vector: list[float] | None = None,
) -> None:
    repository.insert_track(
        track_row={
            "id": track_id,
            "job_id": "job-1",
            "source_id": "source-a",
            "site_id": "site-local-01",
            "camera_id": "cam-source-a",
            "camera_name": "Bangkok Market Camera",
            "label": label,
            "detector_label": detector_label,
            "first_seen_at": first_seen_at,
            "middle_seen_at": first_seen_at,
            "last_seen_at": last_seen_at,
            "first_seen_offset_ms": 0,
            "middle_seen_offset_ms": 400,
            "last_seen_offset_ms": 800,
            "segment_path": "/recordings/source-a/segment.mp4",
            "segment_start_at": first_seen_at,
            "segment_duration_sec": 60.0,
            "frame_count": 5,
            "sample_fps": 2.0,
            "max_confidence": 0.9,
            "avg_confidence": 0.8,
            "first_bbox_json": json.dumps([10, 20, 30, 40]),
            "middle_bbox_json": json.dumps([12, 22, 32, 42]),
            "last_bbox_json": json.dumps([14, 24, 34, 44]),
            "first_point_json": json.dumps({"x": 20, "y": 30}),
            "middle_point_json": json.dumps({"x": 22, "y": 32}),
            "last_point_json": json.dumps({"x": 24, "y": 34}),
            "embedding_status": "ready" if object_vector is not None else "disabled",
            "embedding_model": "test-object-model",
            "embedding_dim": len(object_vector) if object_vector is not None else None,
            "face_status": "ready" if face_vector is not None else "skipped",
            "face_model": "test-face-model",
            "face_dim": len(face_vector) if face_vector is not None else None,
            "closed_reason": "completed",
            "created_at": last_seen_at,
        },
        artifacts=[],
        embedding=(
            {
                "track_id": track_id,
                "model_name": "test-object-model",
                "vector_json": json.dumps(object_vector),
                "created_at": last_seen_at,
            }
            if object_vector is not None
            else None
        ),
        face_embedding=(
            {
                "track_id": track_id,
                "model_name": "test-face-model",
                "vector_json": json.dumps(face_vector),
                "created_at": last_seen_at,
            }
            if face_vector is not None
            else None
        ),
    )


def _image_data_url() -> str:
    image = np.zeros((32, 32, 3), dtype=np.uint8)
    ok, encoded = cv2.imencode(".jpg", image)
    assert ok
    return "data:image/jpeg;base64," + base64.b64encode(encoded.tobytes()).decode("ascii")


def _build_repository(tmp_path) -> VisionRepository:
    repository = VisionRepository(str(tmp_path / "vision.sqlite3"))
    repository.sync_sources(
        [
            _source_row("source-a", updated_at="2026-03-10T15:00:00+00:00"),
        ]
    )
    repository.create_job(
        job_id="job-1",
        source_ids=["source-a"],
        sampled_fps=2.0,
        started_at="2026-03-10T15:00:00+00:00",
    )
    return repository


def test_text_search_falls_back_to_track_metadata(tmp_path) -> None:
    repository = _build_repository(tmp_path)
    _insert_track(
        repository,
        track_id="trk-person",
        label="person",
        detector_label="person",
        first_seen_at="2026-03-10T15:01:00+00:00",
        last_seen_at="2026-03-10T15:01:05+00:00",
    )
    _insert_track(
        repository,
        track_id="trk-vehicle",
        label="vehicle",
        detector_label="car",
        first_seen_at="2026-03-10T15:02:00+00:00",
        last_seen_at="2026-03-10T15:02:05+00:00",
    )

    service = _service_with_repository(
        repository,
        object_embedder=_ObjectEmbedderStub(),
        face_embedder=_FaceEmbedderStub(),
    )

    result = service.search_crop_tracks(text_query="person", page=1, page_size=10)

    assert result["searchModes"] == ["text-fallback"]
    assert result["totalCount"] == 1
    assert result["tracks"][0]["id"] == "trk-person"
    assert result["tracks"][0]["searchReason"] == "text-fallback"


def test_image_search_prefers_face_embeddings_before_object_embeddings(tmp_path) -> None:
    repository = _build_repository(tmp_path)
    _insert_track(
        repository,
        track_id="trk-person-face",
        label="person",
        detector_label="person",
        first_seen_at="2026-03-10T15:01:00+00:00",
        last_seen_at="2026-03-10T15:01:05+00:00",
        object_vector=[0.1, 0.9, 0.0],
        face_vector=[1.0, 0.0, 0.0],
    )

    object_embedder = _ObjectEmbedderStub(image_vector=[0.0, 1.0, 0.0])
    face_embedder = _FaceEmbedderStub(status="ready", vector=[1.0, 0.0, 0.0])
    service = _service_with_repository(
        repository,
        object_embedder=object_embedder,
        face_embedder=face_embedder,
    )

    result = service.search_crop_tracks(image_base64=_image_data_url(), page=1, page_size=5)

    assert result["searchModes"] == ["face-image"]
    assert result["totalCount"] == 1
    assert result["tracks"][0]["id"] == "trk-person-face"
    assert result["tracks"][0]["searchReason"] == "face-image"
    assert face_embedder.calls == 1
    assert object_embedder.image_calls == 0


def test_text_and_image_queries_merge_results_and_reasons(tmp_path) -> None:
    repository = _build_repository(tmp_path)
    _insert_track(
        repository,
        track_id="trk-person-combined",
        label="person",
        detector_label="person",
        first_seen_at="2026-03-10T15:01:00+00:00",
        last_seen_at="2026-03-10T15:01:05+00:00",
        object_vector=[1.0, 0.0, 0.0],
    )
    _insert_track(
        repository,
        track_id="trk-vehicle-image-only",
        label="vehicle",
        detector_label="car",
        first_seen_at="2026-03-10T15:02:00+00:00",
        last_seen_at="2026-03-10T15:02:05+00:00",
        object_vector=[0.4, 0.6, 0.0],
    )

    object_embedder = _ObjectEmbedderStub(
        text_vector=[1.0, 0.0, 0.0],
        image_vector=[0.4, 0.6, 0.0],
    )
    service = _service_with_repository(
        repository,
        object_embedder=object_embedder,
        face_embedder=_FaceEmbedderStub(status="no-face"),
    )

    result = service.search_crop_tracks(
        text_query="person",
        image_base64=_image_data_url(),
        page=1,
        page_size=10,
    )

    assert result["searchModes"] == ["image", "text"]
    assert result["totalCount"] == 2
    assert result["tracks"][0]["id"] == "trk-person-combined"
    assert result["tracks"][0]["searchReason"] == "image+text"
    assert {track["id"] for track in result["tracks"]} == {
        "trk-person-combined",
        "trk-vehicle-image-only",
    }
