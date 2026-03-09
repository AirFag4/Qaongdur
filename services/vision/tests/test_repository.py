from __future__ import annotations

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


def test_sync_sources_retires_missing_sources(tmp_path) -> None:
    repository = VisionRepository(str(tmp_path / "vision.sqlite3"))

    repository.sync_sources(
        [
            _source_row("source-a", updated_at="2026-03-09T10:00:00+00:00"),
            _source_row("source-b", updated_at="2026-03-09T10:00:00+00:00"),
        ]
    )

    repository.sync_sources(
        [
            _source_row("source-b", updated_at="2026-03-09T11:00:00+00:00"),
        ]
    )

    active_sources = repository.list_sources()
    all_sources = repository.list_sources(include_retired=True)

    assert [row["id"] for row in active_sources] == ["source-b"]
    assert {row["id"] for row in all_sources} == {"source-a", "source-b"}
    retired_row = next(row for row in all_sources if row["id"] == "source-a")
    assert retired_row["retired_at"] == "2026-03-09T11:00:00+00:00"

