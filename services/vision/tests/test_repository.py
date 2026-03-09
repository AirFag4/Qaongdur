from __future__ import annotations

import json

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


def test_list_crop_tracks_paginates_results(tmp_path) -> None:
    repository = VisionRepository(str(tmp_path / "vision.sqlite3"))
    repository.sync_sources(
        [
            _source_row("source-a", updated_at="2026-03-09T10:00:00+00:00"),
        ]
    )
    repository.create_job(
        job_id="job-1",
        source_ids=["source-a"],
        sampled_fps=2.0,
        started_at="2026-03-09T10:00:00+00:00",
    )

    for index in range(25):
        repository.insert_track(
            track_row={
                "id": f"trk-{index:02d}",
                "job_id": "job-1",
                "source_id": "source-a",
                "site_id": "site-local-01",
                "camera_id": "cam-source-a",
                "camera_name": "Camera source-a",
                "label": "person" if index % 2 == 0 else "vehicle",
                "detector_label": "person" if index % 2 == 0 else "car",
                "first_seen_at": f"2026-03-09T10:{index:02d}:00+00:00",
                "middle_seen_at": f"2026-03-09T10:{index:02d}:10+00:00",
                "last_seen_at": f"2026-03-09T10:{index:02d}:20+00:00",
                "first_seen_offset_ms": index * 1_000,
                "middle_seen_offset_ms": index * 1_000 + 500,
                "last_seen_offset_ms": index * 1_000 + 900,
                "segment_path": f"/recordings/source-a/{index:02d}.mp4",
                "segment_start_at": f"2026-03-09T10:{index:02d}:00+00:00",
                "segment_duration_sec": 60.0,
                "frame_count": 5,
                "sample_fps": 2.0,
                "max_confidence": 0.9,
                "avg_confidence": 0.75,
                "first_bbox_json": json.dumps([10, 20, 30, 40]),
                "middle_bbox_json": json.dumps([12, 22, 32, 42]),
                "last_bbox_json": json.dumps([14, 24, 34, 44]),
                "first_point_json": json.dumps({"x": 20, "y": 30}),
                "middle_point_json": json.dumps({"x": 22, "y": 32}),
                "last_point_json": json.dumps({"x": 24, "y": 34}),
                "embedding_status": "ready",
                "embedding_model": "mock",
                "embedding_dim": 3,
                "face_status": "skipped",
                "face_model": "mock-face",
                "face_dim": None,
                "closed_reason": "end-of-source",
                "created_at": f"2026-03-09T10:{index:02d}:30+00:00",
            },
            artifacts=[],
            embedding=None,
            face_embedding=None,
        )

    result = repository.list_crop_tracks(page=2, page_size=20)

    assert result["totalCount"] == 25
    assert result["page"] == 2
    assert result["pageSize"] == 20
    assert result["totalPages"] == 2
    assert len(result["tracks"]) == 5
    assert result["tracks"][0]["id"] == "trk-04"
    assert result["tracks"][-1]["id"] == "trk-00"
