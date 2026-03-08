from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from threading import Lock
from typing import Any


SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS video_source (
  id TEXT PRIMARY KEY,
  site_id TEXT NOT NULL,
  camera_id TEXT NOT NULL,
  camera_name TEXT NOT NULL,
  file_path TEXT NOT NULL,
  duration_sec REAL NOT NULL,
  frame_width INTEGER NOT NULL,
  frame_height INTEGER NOT NULL,
  source_fps REAL NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS processing_job (
  id TEXT PRIMARY KEY,
  status TEXT NOT NULL,
  source_ids_json TEXT NOT NULL,
  sampled_fps REAL NOT NULL,
  track_count INTEGER NOT NULL DEFAULT 0,
  started_at TEXT NOT NULL,
  finished_at TEXT,
  detail TEXT
);

CREATE TABLE IF NOT EXISTS track (
  id TEXT PRIMARY KEY,
  job_id TEXT NOT NULL REFERENCES processing_job(id) ON DELETE CASCADE,
  source_id TEXT NOT NULL REFERENCES video_source(id) ON DELETE CASCADE,
  site_id TEXT NOT NULL,
  camera_id TEXT NOT NULL,
  camera_name TEXT NOT NULL,
  label TEXT NOT NULL,
  detector_label TEXT NOT NULL,
  first_seen_at TEXT NOT NULL,
  middle_seen_at TEXT NOT NULL,
  last_seen_at TEXT NOT NULL,
  first_seen_offset_ms INTEGER NOT NULL,
  middle_seen_offset_ms INTEGER NOT NULL,
  last_seen_offset_ms INTEGER NOT NULL,
  frame_count INTEGER NOT NULL,
  sample_fps REAL NOT NULL,
  max_confidence REAL NOT NULL,
  avg_confidence REAL NOT NULL,
  first_bbox_json TEXT NOT NULL,
  middle_bbox_json TEXT NOT NULL,
  last_bbox_json TEXT NOT NULL,
  embedding_status TEXT NOT NULL,
  embedding_model TEXT,
  embedding_dim INTEGER,
  face_status TEXT NOT NULL,
  face_model TEXT,
  face_dim INTEGER,
  closed_reason TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS storage_artifact (
  id TEXT PRIMARY KEY,
  track_id TEXT NOT NULL REFERENCES track(id) ON DELETE CASCADE,
  source_id TEXT NOT NULL,
  role TEXT NOT NULL,
  kind TEXT NOT NULL,
  relative_path TEXT NOT NULL,
  mime_type TEXT NOT NULL,
  byte_size INTEGER NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS track_embedding (
  track_id TEXT PRIMARY KEY REFERENCES track(id) ON DELETE CASCADE,
  model_name TEXT NOT NULL,
  vector_json TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS track_face_embedding (
  track_id TEXT PRIMARY KEY REFERENCES track(id) ON DELETE CASCADE,
  model_name TEXT NOT NULL,
  vector_json TEXT,
  created_at TEXT NOT NULL
);
"""


class VisionRepository:
    def __init__(self, database_path: str) -> None:
        self._database_path = Path(database_path)
        self._database_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()
        with self._connect() as connection:
            connection.executescript(SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            self._database_path,
            check_same_thread=False,
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    def upsert_sources(self, sources: list[dict[str, Any]]) -> None:
        with self._lock, self._connect() as connection:
            connection.executemany(
                """
                INSERT INTO video_source (
                  id, site_id, camera_id, camera_name, file_path, duration_sec,
                  frame_width, frame_height, source_fps, updated_at
                ) VALUES (
                  :id, :site_id, :camera_id, :camera_name, :file_path, :duration_sec,
                  :frame_width, :frame_height, :source_fps, :updated_at
                )
                ON CONFLICT(id) DO UPDATE SET
                  site_id=excluded.site_id,
                  camera_id=excluded.camera_id,
                  camera_name=excluded.camera_name,
                  file_path=excluded.file_path,
                  duration_sec=excluded.duration_sec,
                  frame_width=excluded.frame_width,
                  frame_height=excluded.frame_height,
                  source_fps=excluded.source_fps,
                  updated_at=excluded.updated_at
                """,
                sources,
            )

    def list_sources(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT
                  source.*,
                  COUNT(track.id) AS track_count
                FROM video_source AS source
                LEFT JOIN track ON track.source_id = source.id
                GROUP BY source.id
                ORDER BY source.camera_name ASC
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def create_job(
        self,
        *,
        job_id: str,
        source_ids: list[str],
        sampled_fps: float,
        started_at: str,
    ) -> dict[str, Any]:
        payload = {
            "id": job_id,
            "status": "running",
            "source_ids_json": json.dumps(source_ids),
            "sampled_fps": sampled_fps,
            "started_at": started_at,
        }
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO processing_job (
                  id, status, source_ids_json, sampled_fps, started_at
                ) VALUES (
                  :id, :status, :source_ids_json, :sampled_fps, :started_at
                )
                """,
                payload,
            )
        return {
            "id": job_id,
            "status": "running",
            "sourceIds": source_ids,
            "sampledFps": sampled_fps,
            "startedAt": started_at,
            "trackCount": 0,
        }

    def finish_job(
        self,
        *,
        job_id: str,
        status: str,
        finished_at: str,
        track_count: int,
        detail: str | None = None,
    ) -> None:
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                UPDATE processing_job
                SET status = ?, finished_at = ?, track_count = ?, detail = ?
                WHERE id = ?
                """,
                (status, finished_at, track_count, detail, job_id),
            )

    def latest_job(self) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM processing_job
                ORDER BY started_at DESC
                LIMIT 1
                """
            ).fetchone()
        if row is None:
            return None
        return {
            "id": row["id"],
            "status": row["status"],
            "sourceIds": json.loads(row["source_ids_json"]),
            "sampledFps": row["sampled_fps"],
            "trackCount": row["track_count"],
            "startedAt": row["started_at"],
            "finishedAt": row["finished_at"],
            "detail": row["detail"],
        }

    def delete_tracks_for_sources(self, source_ids: list[str]) -> list[str]:
        if not source_ids:
            return []
        placeholders = ",".join(["?"] * len(source_ids))
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT artifact.relative_path
                FROM storage_artifact AS artifact
                JOIN track ON track.id = artifact.track_id
                WHERE track.source_id IN ({placeholders})
                """,
                source_ids,
            ).fetchall()
            connection.execute(
                f"DELETE FROM track WHERE source_id IN ({placeholders})",
                source_ids,
            )
        return [row["relative_path"] for row in rows]

    def used_storage_bytes(self) -> int:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT COALESCE(SUM(byte_size), 0) AS used_bytes FROM storage_artifact"
            ).fetchone()
        return int(row["used_bytes"] if row else 0)

    def prune_oldest_tracks_until_fit(
        self,
        *,
        storage_limit_bytes: int,
        bytes_needed: int,
    ) -> list[str]:
        deleted_paths: list[str] = []
        with self._lock, self._connect() as connection:
            while True:
                row = connection.execute(
                    "SELECT COALESCE(SUM(byte_size), 0) AS used_bytes FROM storage_artifact"
                ).fetchone()
                used_bytes = int(row["used_bytes"] if row else 0)
                if used_bytes + bytes_needed <= storage_limit_bytes:
                    break

                oldest_track = connection.execute(
                    "SELECT id FROM track ORDER BY created_at ASC LIMIT 1"
                ).fetchone()
                if oldest_track is None:
                    break

                paths = connection.execute(
                    "SELECT relative_path FROM storage_artifact WHERE track_id = ?",
                    (oldest_track["id"],),
                ).fetchall()
                deleted_paths.extend(path["relative_path"] for path in paths)
                connection.execute("DELETE FROM track WHERE id = ?", (oldest_track["id"],))
        return deleted_paths

    def insert_track(
        self,
        *,
        track_row: dict[str, Any],
        artifacts: list[dict[str, Any]],
        embedding: dict[str, Any] | None,
        face_embedding: dict[str, Any] | None,
    ) -> None:
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO track (
                  id, job_id, source_id, site_id, camera_id, camera_name, label,
                  detector_label, first_seen_at, middle_seen_at, last_seen_at,
                  first_seen_offset_ms, middle_seen_offset_ms, last_seen_offset_ms,
                  frame_count, sample_fps, max_confidence, avg_confidence,
                  first_bbox_json, middle_bbox_json, last_bbox_json,
                  embedding_status, embedding_model, embedding_dim,
                  face_status, face_model, face_dim, closed_reason, created_at
                ) VALUES (
                  :id, :job_id, :source_id, :site_id, :camera_id, :camera_name, :label,
                  :detector_label, :first_seen_at, :middle_seen_at, :last_seen_at,
                  :first_seen_offset_ms, :middle_seen_offset_ms, :last_seen_offset_ms,
                  :frame_count, :sample_fps, :max_confidence, :avg_confidence,
                  :first_bbox_json, :middle_bbox_json, :last_bbox_json,
                  :embedding_status, :embedding_model, :embedding_dim,
                  :face_status, :face_model, :face_dim, :closed_reason, :created_at
                )
                """,
                track_row,
            )
            connection.executemany(
                """
                INSERT INTO storage_artifact (
                  id, track_id, source_id, role, kind, relative_path,
                  mime_type, byte_size, created_at
                ) VALUES (
                  :id, :track_id, :source_id, :role, :kind, :relative_path,
                  :mime_type, :byte_size, :created_at
                )
                """,
                artifacts,
            )
            if embedding is not None:
                connection.execute(
                    """
                    INSERT INTO track_embedding (
                      track_id, model_name, vector_json, created_at
                    ) VALUES (
                      :track_id, :model_name, :vector_json, :created_at
                    )
                    """,
                    embedding,
                )
            if face_embedding is not None:
                connection.execute(
                    """
                    INSERT INTO track_face_embedding (
                      track_id, model_name, vector_json, created_at
                    ) VALUES (
                      :track_id, :model_name, :vector_json, :created_at
                    )
                    """,
                    face_embedding,
                )

    def list_crop_tracks(
        self,
        *,
        source_id: str | None = None,
        label: str | None = None,
    ) -> list[dict[str, Any]]:
        conditions: list[str] = []
        params: list[Any] = []
        if source_id:
            conditions.append("track.source_id = ?")
            params.append(source_id)
        if label and label != "all":
            conditions.append("track.label = ?")
            params.append(label)
        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        with self._connect() as connection:
            track_rows = connection.execute(
                f"""
                SELECT track.*
                FROM track
                {where_clause}
                ORDER BY track.last_seen_at DESC
                """,
                params,
            ).fetchall()
            result: list[dict[str, Any]] = []
            for track_row in track_rows:
                asset_rows = connection.execute(
                    """
                    SELECT role, relative_path
                    FROM storage_artifact
                    WHERE track_id = ?
                    ORDER BY created_at ASC
                    """,
                    (track_row["id"],),
                ).fetchall()
                assets = {asset["role"]: asset["relative_path"] for asset in asset_rows}
                result.append(
                    {
                        **dict(track_row),
                        "assets": assets,
                    }
                )
        return result

    def storage_status(self, storage_limit_bytes: int) -> dict[str, Any]:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                  COALESCE(SUM(byte_size), 0) AS used_bytes,
                  COUNT(*) AS artifact_count
                FROM storage_artifact
                """
            ).fetchone()
        used_bytes = int(row["used_bytes"] if row else 0)
        artifact_count = int(row["artifact_count"] if row else 0)
        return {
            "usedBytes": used_bytes,
            "limitBytes": storage_limit_bytes,
            "artifactCount": artifact_count,
            "freeBytes": max(storage_limit_bytes - used_bytes, 0),
        }
