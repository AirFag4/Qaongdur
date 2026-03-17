from __future__ import annotations

import base64
import hashlib
import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Event, Thread
import time
from uuid import uuid5, NAMESPACE_URL

from celery import Celery

from .artifact_store import ArtifactStore
from .config import Settings
from .database import VisionRepository
from .distributed_models import (
    JobResultsEnvelope,
    JobStatusEnvelope,
    WorkerHeartbeatEnvelope,
    WorkerRegistrationEnvelope,
)
from .domain import VisionSource, utcnow_iso
from .object_store import ObjectStoreClient, ObjectStoreError
from .pipeline import VisionPipelineService

LOGGER = logging.getLogger(__name__)


def _parse_segment_start(segment_path: Path) -> datetime | None:
    try:
        return datetime.strptime(segment_path.stem, "%Y-%m-%d_%H-%M-%S-%f").replace(tzinfo=UTC)
    except ValueError:
        return None


class DistributedVisionService:
    def __init__(
        self,
        *,
        settings: Settings,
        query_pipeline: VisionPipelineService,
    ) -> None:
        self._settings = settings
        self._query_pipeline = query_pipeline
        self._repository = VisionRepository(settings.database_path)
        self._artifact_store = ArtifactStore(
            artifacts_dir=settings.artifacts_dir,
            crop_jpeg_quality=settings.crop_jpeg_quality,
            crop_max_dimension=settings.crop_max_dimension,
            frame_max_dimension=settings.frame_max_dimension,
        )
        self._object_store = ObjectStoreClient(
            endpoint=settings.object_storage_endpoint,
            access_key=settings.object_storage_access_key,
            secret_key=settings.object_storage_secret_key,
        )
        self._celery = Celery(
            "qaongdur-vision-api",
            broker=settings.queue_broker_url,
            backend=settings.queue_result_backend,
        )
        self._wake_scanner = Event()
        self._scanner_thread = Thread(
            target=self._scanner_loop,
            daemon=True,
            name="vision-distributed-scanner",
        )
        if settings.segment_upload_enabled:
            self._scanner_thread.start()

    def get_status(self) -> dict[str, object]:
        base_status = self._query_pipeline.get_status()
        workers = self._repository.list_analytic_workers()
        queue_rows = self._repository.list_queue_status()
        return {
            **base_status,
            "executionMode": "api",
            "distributed": {
                "segmentUploadEnabled": self._settings.segment_upload_enabled,
                "workerCount": len(workers),
                "healthyWorkerCount": sum(1 for worker in workers if worker["status"] == "healthy"),
                "queueCount": len(queue_rows),
            },
        }

    def trigger_scan(self) -> dict[str, object]:
        self._wake_scanner.set()
        return {
            "requested": True,
            "requestedAt": utcnow_iso(),
            "detail": "Requested an immediate distributed recordings scan.",
        }

    def register_worker(self, body: WorkerRegistrationEnvelope) -> dict[str, object]:
        checked_at = utcnow_iso()
        self._repository.register_analytic_worker(
            worker_id=body.workerId,
            node_name=body.node.name,
            ssh_alias=body.node.sshAlias,
            hostname=body.node.hostname,
            gpu_available=body.node.gpuAvailable,
            gpu_name=body.node.gpuName,
            docker_version=body.node.dockerVersion,
            nvidia_runtime_version=body.node.nvidiaRuntimeVersion,
            worker_name=body.worker.workerName,
            queue_names=body.worker.queueNames,
            capacity_slots=body.worker.capacitySlots,
            supports_face=body.worker.supportsFace,
            supports_text_embedding=body.worker.supportsTextEmbedding,
            supports_image_embedding=body.worker.supportsImageEmbedding,
            supports_gpu=body.worker.supportsGpu,
            face_model=body.worker.faceModel,
            embedding_model=body.worker.embeddingModel,
            detector_model=body.worker.detectorModel,
            registered_at=checked_at,
        )
        return {
            "registered": True,
            "workerId": body.workerId,
            "checkedAt": checked_at,
        }

    def heartbeat_worker(self, body: WorkerHeartbeatEnvelope) -> dict[str, object]:
        self._repository.heartbeat_analytic_worker(
            worker_id=body.workerId,
            status=body.status,
            active_jobs=body.activeJobs,
            queue_depth_hint=body.queueDepthHint,
            runtime=body.runtime.model_dump(),
            checked_at=body.checkedAt,
        )
        return {
            "accepted": True,
            "workerId": body.workerId,
            "checkedAt": body.checkedAt,
        }

    def update_job_status(self, *, job_id: str, body: JobStatusEnvelope) -> dict[str, object]:
        metrics = body.metrics or {}
        track_count = metrics.get("tracksClosed")
        duration_sec = body.durationSec
        if duration_sec is None:
            duration_ms = metrics.get("durationMs")
            if isinstance(duration_ms, int | float):
                duration_sec = float(duration_ms) / 1000.0
        self._repository.update_job_status(
            job_id=job_id,
            status=body.status,
            worker_id=body.workerId,
            detail=body.detail,
            checked_at=utcnow_iso(),
            track_count=int(track_count) if isinstance(track_count, int | float) else None,
            duration_sec=duration_sec,
        )
        return {
            "updated": True,
            "jobId": job_id,
            "status": body.status,
        }

    def apply_job_results(self, *, job_id: str, body: JobResultsEnvelope) -> dict[str, object]:
        deleted_paths = self._repository.delete_tracks_for_job(job_id=job_id)
        for relative_path in deleted_paths:
            self._artifact_store.delete_relative_path(relative_path)

        stored_tracks = 0
        for bundle in body.trackBundles:
            payloads = []
            for artifact in bundle.artifacts:
                artifact_bytes = base64.b64decode(artifact.payloadBase64)
                track_id = str(bundle.trackRow["id"])
                asset_seed = f"{track_id}::{artifact.role}"
                payloads.append(
                    {
                        "id": f"asset-{uuid5(NAMESPACE_URL, asset_seed).hex[:10]}",
                        "track_id": track_id,
                        "source_id": str(bundle.trackRow["source_id"]),
                        "role": artifact.role,
                        "kind": artifact.kind,
                        "relative_path": f"tracks/{track_id}/{artifact.role}.jpg",
                        "mime_type": artifact.mimeType,
                        "byte_size": len(artifact_bytes),
                        "created_at": utcnow_iso(),
                        "payload": artifact_bytes,
                    }
                )
            required_bytes = sum(int(artifact["byte_size"]) for artifact in payloads)
            pruned_paths = self._repository.prune_oldest_tracks_until_fit(
                storage_limit_bytes=self._settings.effective_storage_limit_bytes,
                bytes_needed=required_bytes,
            )
            for relative_path in pruned_paths:
                self._artifact_store.delete_relative_path(relative_path)
            persisted_artifacts = []
            for artifact in payloads:
                self._artifact_store.write_bytes(
                    str(artifact["relative_path"]),
                    bytes(artifact.pop("payload")),
                )
                persisted_artifacts.append(artifact)

            track_row = dict(bundle.trackRow)
            track_row["job_id"] = job_id
            self._repository.insert_track(
                track_row=track_row,
                artifacts=persisted_artifacts,
                embedding=dict(bundle.embedding),
                face_embedding=dict(bundle.faceEmbedding) if bundle.faceEmbedding else None,
            )
            stored_tracks += 1
        return {
            "stored": True,
            "jobId": job_id,
            "trackCount": stored_tracks,
            "workerId": body.workerId,
        }

    def list_workers(self) -> dict[str, object]:
        workers = self._repository.list_analytic_workers()
        return {
            "count": len(workers),
            "workers": [self._serialize_worker(worker) for worker in workers],
        }

    def list_nodes(self) -> dict[str, object]:
        nodes = self._repository.list_analytic_nodes()
        return {
            "count": len(nodes),
            "nodes": [
                {
                    "id": row["id"],
                    "name": row["name"],
                    "sshAlias": row["ssh_alias"],
                    "hostname": row["hostname"],
                    "status": row["status"],
                    "drainMode": bool(row["drain_mode"]),
                    "gpuAvailable": bool(row["gpu_available"]),
                    "gpuName": row["gpu_name"],
                    "dockerVersion": row["docker_version"],
                    "nvidiaRuntimeVersion": row["nvidia_runtime_version"],
                    "lastHeartbeatAt": row["last_heartbeat_at"],
                    "firstRegisteredAt": row["first_registered_at"],
                    "updatedAt": row["updated_at"],
                    "workerCount": int(row["worker_count"] or 0),
                    "healthyWorkerCount": int(row["healthy_worker_count"] or 0),
                    "offlineWorkerCount": int(row["offline_worker_count"] or 0),
                }
                for row in nodes
            ],
        }

    def list_queues(self) -> dict[str, object]:
        queues = self._repository.list_queue_status()
        return {
            "count": len(queues),
            "queues": [
                {
                    "queueName": row["queue_name"],
                    "queuedCount": int(row["queued_count"] or 0),
                    "runningCount": int(row["running_count"] or 0),
                    "completedCount": int(row["completed_count"] or 0),
                    "failedCount": int(row["failed_count"] or 0),
                }
                for row in queues
            ],
        }

    def _serialize_worker(self, worker: dict[str, object]) -> dict[str, object]:
        return {
            "id": worker["id"],
            "workerName": worker["worker_name"],
            "status": worker["status"],
            "queueNames": worker["queue_names"],
            "capacitySlots": int(worker["capacity_slots"]),
            "activeJobs": int(worker["active_jobs"]),
            "queueDepthHint": int(worker["queue_depth_hint"]),
            "supportsFace": bool(worker["supports_face"]),
            "supportsTextEmbedding": bool(worker["supports_text_embedding"]),
            "supportsImageEmbedding": bool(worker["supports_image_embedding"]),
            "supportsGpu": bool(worker["supports_gpu"]),
            "faceModel": worker["face_model"],
            "embeddingModel": worker["embedding_model"],
            "detectorModel": worker["detector_model"],
            "lastHeartbeatAt": worker["last_heartbeat_at"],
            "registeredAt": worker["registered_at"],
            "updatedAt": worker["updated_at"],
            "runtime": worker["runtime"],
            "node": {
                "name": worker["node_name"],
                "sshAlias": worker["node_ssh_alias"],
                "hostname": worker["node_hostname"],
                "gpuAvailable": bool(worker["node_gpu_available"]),
                "gpuName": worker["node_gpu_name"],
                "dockerVersion": worker["node_docker_version"],
                "nvidiaRuntimeVersion": worker["node_nvidia_runtime_version"],
            },
        }

    def _scanner_loop(self) -> None:
        while True:
            try:
                self._query_pipeline.refresh_sources()
                offline_before = (
                    datetime.now(tz=UTC)
                    - timedelta(seconds=self._settings.worker_offline_timeout_seconds)
                ).isoformat()
                self._repository.mark_stale_workers_offline(offline_before=offline_before)
                self._scan_recording_segments()
            except Exception:  # pragma: no cover - runtime integration path
                LOGGER.exception("Distributed recordings scan failed")

            self._wake_scanner.wait(self._settings.segment_poll_interval_seconds)
            self._wake_scanner.clear()

    def _scan_recording_segments(self) -> None:
        recordings_root = Path(self._settings.recordings_dir)
        if not recordings_root.exists():
            return

        self._object_store.ensure_bucket(self._settings.object_storage_bucket)
        known_segments = self._repository.list_recording_segment_index()
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
        segment_candidates: list[tuple[float, int, Path]] = []
        for candidate in recordings_root.rglob("*.mp4"):
            try:
                stat_result = candidate.stat()
            except FileNotFoundError:
                continue
            segment_candidates.append((stat_result.st_mtime, stat_result.st_size, candidate))

        segment_candidates.sort(key=lambda item: item[0], reverse=True)
        for segment_mtime, segment_size, segment_path in segment_candidates:
            try:
                relative_path = segment_path.relative_to(recordings_root)
            except ValueError:
                continue
            if len(relative_path.parts) < 2:
                continue
            if now - segment_mtime < self._settings.segment_min_age_seconds:
                continue

            path_name = relative_path.parts[0]
            source = sources_by_path.get(path_name)
            if source is None:
                continue
            segment_start_at = _parse_segment_start(segment_path)
            if segment_start_at is None:
                continue

            object_key = self._build_segment_object_key(
                source=source,
                segment_path=segment_path,
                segment_start_at=segment_start_at,
            )
            known_segment = known_segments.get(str(segment_path))
            known_sha256 = None
            object_uploaded = False
            if known_segment is not None and int(known_segment.get("byte_size") or 0) == segment_size:
                known_sha256 = str(known_segment.get("sha256") or "") or None
                object_uploaded = (
                    str(known_segment.get("storage_status") or "") == "uploaded"
                    and str(known_segment.get("object_bucket") or "") == self._settings.object_storage_bucket
                    and str(known_segment.get("object_key") or "") == object_key
                    and known_sha256 is not None
                )
                if object_uploaded and str(known_segment.get("status") or "") in {
                    "queued",
                    "processing",
                    "processed",
                    "failed",
                }:
                    continue

            try:
                sha256 = known_sha256 or self._sha256_for_file(segment_path)
                if not object_uploaded and not self._object_store.object_exists(
                    self._settings.object_storage_bucket,
                    object_key,
                ):
                    self._object_store.upload_file(
                        bucket_name=self._settings.object_storage_bucket,
                        object_key=object_key,
                        file_path=str(segment_path),
                        content_type="video/mp4",
                    )
            except FileNotFoundError:
                continue
            self._repository.register_uploaded_segment(
                segment_path=str(segment_path),
                source_id=source.id,
                path_name=source.path_name,
                camera_id=source.camera_id,
                camera_name=source.camera_name,
                segment_start_at=segment_start_at.isoformat(),
                byte_size=segment_size,
                sha256=sha256,
                object_bucket=self._settings.object_storage_bucket,
                object_key=object_key,
                created_at=utcnow_iso(),
                uploaded_at=utcnow_iso(),
            )

            job_id = self._job_id_for_segment(segment_path=str(segment_path))
            queue_name = (
                self._settings.job_face_queue
                if self._settings.face_enabled
                else self._settings.job_default_queue
            )
            inserted = self._repository.create_distributed_job(
                job_id=job_id,
                source_ids=[source.id],
                sampled_fps=self._effective_sample_fps(),
                requested_at=utcnow_iso(),
                queue_name=queue_name,
                segment_path=str(segment_path),
                detail=f"Queued {segment_path.name} for distributed processing.",
            )
            if not inserted:
                continue

            known_segments[str(segment_path)] = {
                "segment_path": str(segment_path),
                "byte_size": segment_size,
                "sha256": sha256,
                "object_bucket": self._settings.object_storage_bucket,
                "object_key": object_key,
                "storage_status": "uploaded",
                "status": "queued",
                "job_id": job_id,
            }

            task_payload = {
                "jobId": job_id,
                "jobType": "process-segment",
                "segmentId": self._segment_id_for_path(str(segment_path)),
                "sourceId": source.id,
                "siteId": source.site_id,
                "cameraId": source.camera_id,
                "cameraName": source.camera_name,
                "segment": {
                    "bucket": self._settings.object_storage_bucket,
                    "objectKey": object_key,
                    "sha256": sha256,
                    "segmentStartAt": segment_start_at.isoformat(),
                    "durationSec": None,
                    "localPath": str(segment_path),
                },
                "pipeline": {
                    "sampleFps": self._effective_sample_fps(),
                    "detectorModel": self._settings.detector_model_name,
                    "embeddingEnabled": self._settings.embedding_enabled,
                    "embeddingModel": self._settings.embedding_model_name,
                    "faceEnabled": self._settings.face_enabled,
                    "faceModel": self._settings.face_model_name,
                },
                "requiredCapabilities": {
                    "supportsTextEmbedding": self._settings.embedding_enabled,
                    "supportsImageEmbedding": self._settings.embedding_enabled,
                    "supportsFace": self._settings.face_enabled,
                    "supportsGpu": False,
                },
                "attemptNo": 1,
                "requestedAt": utcnow_iso(),
            }
            self._celery.send_task(
                "vision.process_segment",
                kwargs={"task_payload": task_payload},
                queue=queue_name,
            )

    def _effective_sample_fps(self) -> float:
        return min(
            max(self._settings.sample_fps, self._settings.min_sample_fps),
            self._settings.max_sample_fps,
        )

    def _job_id_for_segment(self, *, segment_path: str) -> str:
        return f"job-{uuid5(NAMESPACE_URL, segment_path).hex[:16]}"

    def _segment_id_for_path(self, segment_path: str) -> str:
        return str(uuid5(NAMESPACE_URL, segment_path))

    def _build_segment_object_key(
        self,
        *,
        source: VisionSource,
        segment_path: Path,
        segment_start_at: datetime,
    ) -> str:
        return (
            f"{self._settings.segment_object_prefix.strip('/')}/"
            f"{source.site_id}/{source.camera_id}/"
            f"{segment_start_at:%Y/%m/%d}/"
            f"{segment_path.name}"
        )

    def _sha256_for_file(self, file_path: Path) -> str:
        digest = hashlib.sha256()
        with file_path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
