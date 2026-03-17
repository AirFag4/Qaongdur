from __future__ import annotations

import sys
from types import ModuleType
from types import SimpleNamespace

from vision_service.config import Settings
from vision_service.database import VisionRepository


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


def test_settings_parse_worker_queue_csv(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("QAONGDUR_VISION_WORKER_QUEUES", "vision.cpu, vision.cpu.face")
    monkeypatch.setenv("QAONGDUR_VISION_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("QAONGDUR_VISION_ARTIFACTS_DIR", str(tmp_path / "artifacts"))
    monkeypatch.setenv(
        "QAONGDUR_VISION_DATABASE_PATH",
        str(tmp_path / "data" / "vision.sqlite3"),
    )
    monkeypatch.setenv(
        "QAONGDUR_VISION_WORKER_RUNTIME_DIR",
        str(tmp_path / "worker-runtime"),
    )

    settings = Settings(_env_file=None)

    assert settings.worker_queues == ["vision.cpu", "vision.cpu.face"]


def test_repository_tracks_distributed_workers_and_jobs(tmp_path) -> None:
    repository = VisionRepository(str(tmp_path / "vision.sqlite3"))
    repository.sync_sources(
        [
            _source_row("source-a", updated_at="2026-03-16T10:00:00+00:00"),
        ]
    )

    inserted_segment = repository.register_uploaded_segment(
        segment_path="/recordings/path-source-a/2026-03-16_10-00-00-000000.mp4",
        source_id="source-a",
        path_name="path-source-a",
        camera_id="cam-source-a",
        camera_name="Camera source-a",
        segment_start_at="2026-03-16T10:00:00+00:00",
        byte_size=1234,
        sha256="abc123",
        object_bucket="qaongdur-dev",
        object_key="recordings/site-local-01/cam-source-a/2026/03/16/segment.mp4",
        created_at="2026-03-16T10:01:00+00:00",
        uploaded_at="2026-03-16T10:01:05+00:00",
    )
    created_job = repository.create_distributed_job(
        job_id="job-dist-1",
        source_ids=["source-a"],
        sampled_fps=2.0,
        requested_at="2026-03-16T10:01:10+00:00",
        queue_name="vision.cpu.face",
        segment_path="/recordings/path-source-a/2026-03-16_10-00-00-000000.mp4",
        detail="Queued for distributed processing.",
    )
    repository.register_analytic_worker(
        worker_id="worker-1",
        node_name="ati-local-home",
        ssh_alias="ati-local-home",
        hostname="ati-local-home.local",
        gpu_available=False,
        gpu_name=None,
        docker_version="29.2.1",
        nvidia_runtime_version=None,
        worker_name="vision-worker-1",
        queue_names=["vision.cpu", "vision.cpu.face"],
        capacity_slots=1,
        supports_face=True,
        supports_text_embedding=True,
        supports_image_embedding=True,
        supports_gpu=False,
        face_model="Megatron",
        embedding_model="MobileCLIP2-S0",
        detector_model="yolo26n.pt",
        registered_at="2026-03-16T10:01:15+00:00",
    )
    repository.heartbeat_analytic_worker(
        worker_id="worker-1",
        status="healthy",
        active_jobs=1,
        queue_depth_hint=0,
        runtime={"cpuPercent": 25.0, "memoryPercent": 30.0},
        checked_at="2026-03-16T10:01:20+00:00",
    )
    repository.update_job_status(
        job_id="job-dist-1",
        status="running",
        worker_id="worker-1",
        detail="Started.",
        checked_at="2026-03-16T10:01:20+00:00",
    )
    repository.update_job_status(
        job_id="job-dist-1",
        status="completed",
        worker_id="worker-1",
        detail="Finished.",
        checked_at="2026-03-16T10:02:20+00:00",
        track_count=3,
        duration_sec=60.0,
    )

    workers = repository.list_analytic_workers()
    nodes = repository.list_analytic_nodes()
    queues = repository.list_queue_status()
    latest_job = repository.latest_job()

    assert inserted_segment is True
    assert created_job is True
    assert workers[0]["queue_names"] == ["vision.cpu", "vision.cpu.face"]
    assert workers[0]["active_jobs"] == 1
    assert nodes[0]["name"] == "ati-local-home"
    assert int(nodes[0]["healthy_worker_count"]) == 1
    assert queues == [
        {
            "queue_name": "vision.cpu.face",
            "queued_count": 0,
            "running_count": 0,
            "completed_count": 1,
            "failed_count": 0,
        }
    ]
    assert latest_job is not None
    assert latest_job["status"] == "completed"
    assert latest_job["trackCount"] == 3


def test_distributed_scan_skips_known_uploaded_segments(monkeypatch, tmp_path) -> None:
    fake_celery = ModuleType("celery")
    fake_minio = ModuleType("minio")
    fake_minio_error = ModuleType("minio.error")

    class _FakeCelery:
        def __init__(self, *args, **kwargs) -> None:
            del args, kwargs

        def send_task(self, *args, **kwargs) -> None:
            del args, kwargs

    fake_celery.Celery = _FakeCelery

    class _FakeMinio:
        def __init__(self, *args, **kwargs) -> None:
            del args, kwargs

    class _FakeS3Error(Exception):
        code = "NoSuchKey"

    fake_minio.Minio = _FakeMinio
    fake_minio_error.S3Error = _FakeS3Error
    monkeypatch.setitem(sys.modules, "celery", fake_celery)
    monkeypatch.setitem(sys.modules, "minio", fake_minio)
    monkeypatch.setitem(sys.modules, "minio.error", fake_minio_error)

    from vision_service.distributed_service import DistributedVisionService

    recordings_dir = tmp_path / "recordings"
    segment_path = recordings_dir / "path-source-a" / "2026-03-16_10-00-00-000000.mp4"
    segment_path.parent.mkdir(parents=True, exist_ok=True)
    segment_path.write_bytes(b"segment-data")

    monkeypatch.setenv("QAONGDUR_VISION_SEGMENT_UPLOAD_ENABLED", "false")
    monkeypatch.setenv("QAONGDUR_VISION_RECORDINGS_DIR", str(recordings_dir))
    monkeypatch.setenv("QAONGDUR_VISION_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("QAONGDUR_VISION_ARTIFACTS_DIR", str(tmp_path / "artifacts"))
    monkeypatch.setenv(
        "QAONGDUR_VISION_DATABASE_PATH",
        str(tmp_path / "data" / "vision.sqlite3"),
    )
    monkeypatch.setenv(
        "QAONGDUR_VISION_WORKER_RUNTIME_DIR",
        str(tmp_path / "worker-runtime"),
    )
    monkeypatch.setenv("QAONGDUR_VISION_SEGMENT_MIN_AGE_SECONDS", "0")

    settings = Settings(_env_file=None)
    settings.ensure_directories()

    repository = VisionRepository(settings.database_path)
    repository.sync_sources(
        [
            _source_row("source-a", updated_at="2026-03-16T10:00:00+00:00"),
        ]
    )
    repository.register_uploaded_segment(
        segment_path=str(segment_path),
        source_id="source-a",
        path_name="path-source-a",
        camera_id="cam-source-a",
        camera_name="Camera source-a",
        segment_start_at="2026-03-16T10:00:00+00:00",
        byte_size=segment_path.stat().st_size,
        sha256="abc123",
        object_bucket="qaongdur-dev",
        object_key="recordings/site-local-01/cam-source-a/2026/03/16/2026-03-16_10-00-00-000000.mp4",
        created_at="2026-03-16T10:01:00+00:00",
        uploaded_at="2026-03-16T10:01:05+00:00",
    )
    repository.create_distributed_job(
        job_id="job-dist-skip-1",
        source_ids=["source-a"],
        sampled_fps=10.0,
        requested_at="2026-03-16T10:01:10+00:00",
        queue_name="vision.cpu.face",
        segment_path=str(segment_path),
        detail="Queued for distributed processing.",
    )

    service = DistributedVisionService(
        settings=settings,
        query_pipeline=SimpleNamespace(get_status=lambda: {}, refresh_sources=lambda: None),
    )
    service._object_store.ensure_bucket = lambda bucket: None
    service._object_store.object_exists = lambda *args, **kwargs: (_ for _ in ()).throw(
        AssertionError("object existence should not be probed for known queued segments")
    )
    service._object_store.upload_file = lambda *args, **kwargs: (_ for _ in ()).throw(
        AssertionError("upload should not be attempted for known queued segments")
    )
    service._sha256_for_file = lambda path: (_ for _ in ()).throw(
        AssertionError("sha256 should not be recomputed for known queued segments")
    )
    queued_tasks: list[tuple[tuple[object, ...], dict[str, object]]] = []
    service._celery = SimpleNamespace(
        send_task=lambda *args, **kwargs: queued_tasks.append((args, kwargs))
    )

    service._scan_recording_segments()

    assert queued_tasks == []
