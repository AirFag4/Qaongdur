from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
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
  path_name TEXT NOT NULL DEFAULT '',
  stream_url TEXT NOT NULL DEFAULT '',
  live_stream_url TEXT,
  health TEXT NOT NULL DEFAULT 'offline',
  source_kind TEXT NOT NULL DEFAULT 'rtsp',
  ingest_mode TEXT NOT NULL DEFAULT 'pull',
  file_path TEXT NOT NULL DEFAULT '',
  duration_sec REAL NOT NULL DEFAULT 0,
  frame_width INTEGER NOT NULL DEFAULT 0,
  frame_height INTEGER NOT NULL DEFAULT 0,
  source_fps REAL NOT NULL DEFAULT 0,
  updated_at TEXT NOT NULL,
  last_segment_at TEXT,
  retired_at TEXT
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

CREATE TABLE IF NOT EXISTS recording_segment (
  segment_path TEXT PRIMARY KEY,
  source_id TEXT NOT NULL REFERENCES video_source(id) ON DELETE CASCADE,
  path_name TEXT NOT NULL,
  camera_id TEXT NOT NULL,
  camera_name TEXT NOT NULL,
  segment_start_at TEXT NOT NULL,
  segment_end_at TEXT,
  duration_sec REAL,
  byte_size INTEGER NOT NULL DEFAULT 0,
  status TEXT NOT NULL,
  job_id TEXT REFERENCES processing_job(id) ON DELETE SET NULL,
  detail TEXT,
  created_at TEXT NOT NULL,
  processed_at TEXT
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
  segment_path TEXT,
  segment_start_at TEXT,
  segment_duration_sec REAL,
  frame_count INTEGER NOT NULL,
  sample_fps REAL NOT NULL,
  max_confidence REAL NOT NULL,
  avg_confidence REAL NOT NULL,
  first_bbox_json TEXT NOT NULL,
  middle_bbox_json TEXT NOT NULL,
  last_bbox_json TEXT NOT NULL,
  first_point_json TEXT,
  middle_point_json TEXT,
  last_point_json TEXT,
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

CREATE INDEX IF NOT EXISTS idx_track_last_seen_at ON track(last_seen_at DESC);
CREATE INDEX IF NOT EXISTS idx_track_camera_time ON track(camera_id, last_seen_at DESC);
CREATE INDEX IF NOT EXISTS idx_segment_source_time ON recording_segment(source_id, segment_start_at DESC);
"""


class VisionRepository:
    def __init__(self, database_path: str) -> None:
        self._database_path = Path(database_path)
        self._database_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()
        with self._connect() as connection:
            connection.executescript(SCHEMA)
            self._migrate(connection)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            self._database_path,
            check_same_thread=False,
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    def _migrate(self, connection: sqlite3.Connection) -> None:
        self._ensure_column(connection, "video_source", "path_name", "TEXT NOT NULL DEFAULT ''")
        self._ensure_column(connection, "video_source", "stream_url", "TEXT NOT NULL DEFAULT ''")
        self._ensure_column(connection, "video_source", "live_stream_url", "TEXT")
        self._ensure_column(connection, "video_source", "health", "TEXT NOT NULL DEFAULT 'offline'")
        self._ensure_column(connection, "video_source", "source_kind", "TEXT NOT NULL DEFAULT 'rtsp'")
        self._ensure_column(connection, "video_source", "ingest_mode", "TEXT NOT NULL DEFAULT 'pull'")
        self._ensure_column(connection, "video_source", "last_segment_at", "TEXT")
        self._ensure_column(connection, "video_source", "retired_at", "TEXT")
        self._ensure_column(connection, "track", "segment_path", "TEXT")
        self._ensure_column(connection, "track", "segment_start_at", "TEXT")
        self._ensure_column(connection, "track", "segment_duration_sec", "REAL")
        self._ensure_column(connection, "track", "first_point_json", "TEXT")
        self._ensure_column(connection, "track", "middle_point_json", "TEXT")
        self._ensure_column(connection, "track", "last_point_json", "TEXT")

    def _ensure_column(
        self,
        connection: sqlite3.Connection,
        table_name: str,
        column_name: str,
        definition: str,
    ) -> None:
        columns = {
            row["name"]
            for row in connection.execute(f"PRAGMA table_info({table_name})").fetchall()
        }
        if column_name in columns:
            return
        connection.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}")

    def sync_sources(self, sources: list[dict[str, Any]]) -> None:
        synced_at = (
            str(sources[0].get("updated_at"))
            if sources and sources[0].get("updated_at")
            else datetime.now(tz=UTC).isoformat()
        )
        active_ids = [str(source["id"]) for source in sources]
        with self._lock, self._connect() as connection:
            connection.executemany(
                """
                INSERT INTO video_source (
                  id, site_id, camera_id, camera_name, path_name, stream_url, live_stream_url,
                  health, source_kind, ingest_mode, file_path, duration_sec, frame_width,
                  frame_height, source_fps, updated_at, last_segment_at, retired_at
                ) VALUES (
                  :id, :site_id, :camera_id, :camera_name, :path_name, :stream_url, :live_stream_url,
                  :health, :source_kind, :ingest_mode, :file_path, :duration_sec, :frame_width,
                  :frame_height, :source_fps, :updated_at, :last_segment_at, :retired_at
                )
                ON CONFLICT(id) DO UPDATE SET
                  site_id=excluded.site_id,
                  camera_id=excluded.camera_id,
                  camera_name=excluded.camera_name,
                  path_name=excluded.path_name,
                  stream_url=excluded.stream_url,
                  live_stream_url=excluded.live_stream_url,
                  health=excluded.health,
                  source_kind=excluded.source_kind,
                  ingest_mode=excluded.ingest_mode,
                  file_path=excluded.file_path,
                  duration_sec=excluded.duration_sec,
                  frame_width=excluded.frame_width,
                  frame_height=excluded.frame_height,
                  source_fps=excluded.source_fps,
                  updated_at=excluded.updated_at,
                  last_segment_at=COALESCE(video_source.last_segment_at, excluded.last_segment_at),
                  retired_at=NULL
                """,
                sources,
            )
            if active_ids:
                placeholders = ", ".join("?" for _ in active_ids)
                connection.execute(
                    f"""
                    UPDATE video_source
                    SET retired_at = COALESCE(retired_at, ?)
                    WHERE id NOT IN ({placeholders})
                    """,
                    [synced_at, *active_ids],
                )
            else:
                connection.execute(
                    """
                    UPDATE video_source
                    SET retired_at = COALESCE(retired_at, ?)
                    """,
                    (synced_at,),
                )

    def list_sources(self, *, include_retired: bool = False) -> list[dict[str, Any]]:
        where_clause = "" if include_retired else "WHERE source.retired_at IS NULL"
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT
                  source.*,
                  COUNT(DISTINCT track.id) AS track_count,
                  COUNT(DISTINCT CASE WHEN segment.status = 'processed' THEN segment.segment_path END)
                    AS processed_segment_count,
                  MAX(segment.processed_at) AS latest_processed_at
                FROM video_source AS source
                LEFT JOIN track ON track.source_id = source.id
                LEFT JOIN recording_segment AS segment ON segment.source_id = source.id
                """
                + where_clause
                + """
                GROUP BY source.id
                ORDER BY source.retired_at IS NOT NULL, source.camera_name ASC
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def get_source_by_path_name(self, path_name: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM video_source WHERE path_name = ? LIMIT 1",
                (path_name,),
            ).fetchone()
        return dict(row) if row else None

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

    def register_segment(
        self,
        *,
        segment_path: str,
        source_id: str,
        path_name: str,
        camera_id: str,
        camera_name: str,
        segment_start_at: str,
        byte_size: int,
        created_at: str,
    ) -> bool:
        with self._lock, self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO recording_segment (
                  segment_path, source_id, path_name, camera_id, camera_name,
                  segment_start_at, byte_size, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?)
                """,
                (
                    segment_path,
                    source_id,
                    path_name,
                    camera_id,
                    camera_name,
                    segment_start_at,
                    byte_size,
                    created_at,
                ),
            )
        return cursor.rowcount > 0

    def mark_segment_processing(
        self,
        *,
        segment_path: str,
        job_id: str,
    ) -> None:
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                UPDATE recording_segment
                SET status = 'processing', job_id = ?, detail = NULL
                WHERE segment_path = ?
                """,
                (job_id, segment_path),
            )

    def mark_segment_processed(
        self,
        *,
        segment_path: str,
        processed_at: str,
        duration_sec: float,
        segment_end_at: str,
        track_count: int,
    ) -> None:
        with self._lock, self._connect() as connection:
            source_row = connection.execute(
                "SELECT source_id FROM recording_segment WHERE segment_path = ?",
                (segment_path,),
            ).fetchone()
            connection.execute(
                """
                UPDATE recording_segment
                SET status = 'processed',
                    processed_at = ?,
                    duration_sec = ?,
                    segment_end_at = ?,
                    detail = ?
                WHERE segment_path = ?
                """,
                (
                    processed_at,
                    duration_sec,
                    segment_end_at,
                    f"{track_count} tracks",
                    segment_path,
                ),
            )
            if source_row is not None:
                connection.execute(
                    "UPDATE video_source SET last_segment_at = ? WHERE id = ?",
                    (processed_at, source_row["source_id"]),
                )

    def mark_segment_failed(
        self,
        *,
        segment_path: str,
        processed_at: str,
        detail: str,
    ) -> None:
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                UPDATE recording_segment
                SET status = 'failed', processed_at = ?, detail = ?
                WHERE segment_path = ?
                """,
                (processed_at, detail[:1000], segment_path),
            )

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
                  segment_path, segment_start_at, segment_duration_sec,
                  frame_count, sample_fps, max_confidence, avg_confidence,
                  first_bbox_json, middle_bbox_json, last_bbox_json,
                  first_point_json, middle_point_json, last_point_json,
                  embedding_status, embedding_model, embedding_dim,
                  face_status, face_model, face_dim, closed_reason, created_at
                ) VALUES (
                  :id, :job_id, :source_id, :site_id, :camera_id, :camera_name, :label,
                  :detector_label, :first_seen_at, :middle_seen_at, :last_seen_at,
                  :first_seen_offset_ms, :middle_seen_offset_ms, :last_seen_offset_ms,
                  :segment_path, :segment_start_at, :segment_duration_sec,
                  :frame_count, :sample_fps, :max_confidence, :avg_confidence,
                  :first_bbox_json, :middle_bbox_json, :last_bbox_json,
                  :first_point_json, :middle_point_json, :last_point_json,
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
                    INSERT OR REPLACE INTO track_embedding (
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
                    INSERT OR REPLACE INTO track_face_embedding (
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
        camera_id: str | None = None,
        label: str | None = None,
        from_at: str | None = None,
        to_at: str | None = None,
        include_retired: bool = False,
        page: int = 1,
        page_size: int = 20,
    ) -> dict[str, Any]:
        conditions: list[str] = []
        params: list[Any] = []
        if not include_retired:
            conditions.append("source.retired_at IS NULL")
        if source_id:
            conditions.append("track.source_id = ?")
            params.append(source_id)
        if camera_id:
            conditions.append("track.camera_id = ?")
            params.append(camera_id)
        if label and label != "all":
            conditions.append("track.label = ?")
            params.append(label)
        if from_at:
            conditions.append("track.last_seen_at >= ?")
            params.append(from_at)
        if to_at:
            conditions.append("track.first_seen_at <= ?")
            params.append(to_at)
        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        page_size = max(page_size, 1)
        page = max(page, 1)
        offset = (page - 1) * page_size
        with self._connect() as connection:
            count_row = connection.execute(
                f"""
                SELECT COUNT(*) AS total_count
                FROM track
                JOIN video_source AS source ON source.id = track.source_id
                {where_clause}
                """,
                params,
            ).fetchone()
            total_count = int(count_row["total_count"] if count_row else 0)
            total_pages = max((total_count + page_size - 1) // page_size, 1)
            safe_page = min(page, total_pages)
            safe_offset = (safe_page - 1) * page_size
            track_rows = connection.execute(
                f"""
                SELECT track.*, source.frame_width AS source_frame_width, source.frame_height AS source_frame_height
                FROM track
                JOIN video_source AS source ON source.id = track.source_id
                {where_clause}
                ORDER BY track.last_seen_at DESC
                LIMIT ? OFFSET ?
                """,
                [*params, page_size, safe_offset],
            ).fetchall()
            return {
                "tracks": [self._hydrate_track(connection, dict(track_row)) for track_row in track_rows],
                "totalCount": total_count,
                "page": safe_page,
                "pageSize": page_size,
                "totalPages": total_pages,
            }

    def purge_retired_sources(
        self,
        *,
        source_kind: str | None = None,
    ) -> list[str]:
        conditions = ["source.retired_at IS NOT NULL"]
        params: list[Any] = []
        if source_kind:
            conditions.append("source.source_kind = ?")
            params.append(source_kind)
        where_clause = " AND ".join(conditions)

        deleted_paths: list[str] = []
        with self._lock, self._connect() as connection:
            artifact_rows = connection.execute(
                f"""
                SELECT artifact.relative_path
                FROM storage_artifact AS artifact
                JOIN track ON track.id = artifact.track_id
                JOIN video_source AS source ON source.id = track.source_id
                WHERE {where_clause}
                """,
                params,
            ).fetchall()
            deleted_paths = [str(row["relative_path"]) for row in artifact_rows]
            delete_conditions = ["retired_at IS NOT NULL"]
            delete_params: list[Any] = []
            if source_kind:
                delete_conditions.append("source_kind = ?")
                delete_params.append(source_kind)
            connection.execute(
                f"DELETE FROM video_source WHERE {' AND '.join(delete_conditions)}",
                delete_params,
            )
        return deleted_paths

    def get_crop_track(self, track_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            track_row = connection.execute(
                """
                SELECT track.*, source.frame_width AS source_frame_width, source.frame_height AS source_frame_height
                FROM track
                JOIN video_source AS source ON source.id = track.source_id
                WHERE track.id = ?
                LIMIT 1
                """,
                (track_id,),
            ).fetchone()
            if track_row is None:
                return None
            return self._hydrate_track(connection, dict(track_row))

    def _hydrate_track(
        self,
        connection: sqlite3.Connection,
        track_row: dict[str, Any],
    ) -> dict[str, Any]:
        asset_rows = connection.execute(
            """
            SELECT role, relative_path
            FROM storage_artifact
            WHERE track_id = ?
            ORDER BY created_at ASC
            """,
            (track_row["id"],),
        ).fetchall()
        embedding_row = connection.execute(
            "SELECT model_name, vector_json FROM track_embedding WHERE track_id = ?",
            (track_row["id"],),
        ).fetchone()
        face_row = connection.execute(
            "SELECT model_name, vector_json FROM track_face_embedding WHERE track_id = ?",
            (track_row["id"],),
        ).fetchone()
        assets = {asset["role"]: asset["relative_path"] for asset in asset_rows}
        return {
            **track_row,
            "assets": assets,
            "embedding_vector_dim": (
                len(json.loads(embedding_row["vector_json"])) if embedding_row else None
            ),
            "face_vector_dim": len(json.loads(face_row["vector_json"]))
            if face_row and face_row["vector_json"]
            else None,
        }

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
