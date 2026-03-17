from __future__ import annotations

import base64
from contextlib import suppress
from dataclasses import dataclass
import logging
from pathlib import Path
import socket
import subprocess
from tempfile import TemporaryDirectory
from threading import Event, Lock, Thread
from typing import Any
from uuid import NAMESPACE_DNS, uuid5

from celery import Celery
import httpx
import psutil

from .config import Settings, get_settings
from .distributed_models import (
    JobResultsEnvelope,
    JobStatusEnvelope,
    TrackArtifactBody,
    TrackBundleBody,
    WorkerHeartbeatEnvelope,
    WorkerHeartbeatRuntime,
    WorkerRegistrationEnvelope,
    WorkerRegistrationBody,
    NodeRegistrationBody,
)
from .domain import VisionSource, utcnow_iso
from .object_store import ObjectStoreClient
from .segment_processor import PreparedTrackBundle, SegmentProcessor

LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class _WorkerState:
    active_jobs: int = 0
    registered: bool = False
    last_error: str | None = None


@dataclass(slots=True)
class _GpuRuntimeInfo:
    available: bool
    name: str | None = None


def _device_requests_gpu(device_name: str) -> bool:
    normalized = device_name.strip().lower() if device_name else "cpu"
    return normalized == "auto" or normalized.startswith("cuda")


def _detect_gpu_runtime() -> _GpuRuntimeInfo:
    try:
        import torch

        if not torch.cuda.is_available():
            return _GpuRuntimeInfo(available=False)
        return _GpuRuntimeInfo(
            available=True,
            name=str(torch.cuda.get_device_name(0)),
        )
    except Exception:
        return _GpuRuntimeInfo(available=False)


class DistributedWorkerRuntime:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._worker_id = settings.worker_id or str(
            uuid5(NAMESPACE_DNS, f"{settings.node_name}:{settings.worker_name}")
        )
        self._state = _WorkerState()
        self._state_lock = Lock()
        self._stop_event = Event()
        self._gpu_info = _detect_gpu_runtime()
        self._gpu_configured = self._gpu_info.available and (
            _device_requests_gpu(settings.detector_device)
            or _device_requests_gpu(settings.embedding_device)
        )
        self._processor = SegmentProcessor(settings)
        self._object_store = ObjectStoreClient(
            endpoint=settings.object_storage_endpoint,
            access_key=settings.object_storage_access_key,
            secret_key=settings.object_storage_secret_key,
        )
        self._http = httpx.Client(
            timeout=settings.internal_api_timeout_seconds,
            headers={"X-QAONGDUR-INTERNAL-TOKEN": settings.internal_service_token},
        )
        self._heartbeat_thread = Thread(
            target=self._heartbeat_loop,
            daemon=True,
            name="vision-worker-heartbeat",
        )

    @property
    def worker_id(self) -> str:
        return self._worker_id

    def start(self) -> None:
        self._register()
        self._heartbeat_thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        with suppress(Exception):
            self._http.close()

    def on_task_start(self) -> None:
        with self._state_lock:
            self._state.active_jobs += 1

    def on_task_end(self) -> None:
        with self._state_lock:
            self._state.active_jobs = max(self._state.active_jobs - 1, 0)

    def process_segment_task(self, task_payload: dict[str, Any]) -> dict[str, object]:
        self.on_task_start()
        job_id = str(task_payload["jobId"])
        try:
            self._post_job_status(
                job_id=job_id,
                body=JobStatusEnvelope(
                    workerId=self._worker_id,
                    status="running",
                    detail=f"Worker {self._settings.worker_name} started processing.",
                    metrics={},
                ),
            )
            result = self._run_segment(task_payload)
            self._post_job_results(job_id=job_id, bundles=result["bundles"], duration_sec=result["durationSec"])
            self._post_job_status(
                job_id=job_id,
                body=JobStatusEnvelope(
                    workerId=self._worker_id,
                    status="completed",
                    detail=(
                        f"Processed {result['trackCount']} tracks from "
                        f"{task_payload['cameraName']} on {self._settings.node_name}."
                    ),
                    durationSec=float(result["durationSec"]),
                    metrics={
                        "framesDecoded": int(result["metrics"]["framesDecoded"]),
                        "framesSampled": int(result["metrics"]["framesSampled"]),
                        "tracksClosed": int(result["metrics"]["tracksClosed"]),
                        "durationMs": int(result["metrics"]["durationMs"]),
                    },
                ),
            )
            return {
                "jobId": result["jobId"],
                "trackCount": result["trackCount"],
                "durationSec": result["durationSec"],
                "metrics": result["metrics"],
            }
        except Exception as error:
            LOGGER.exception("Worker failed to process job %s", job_id)
            self._post_job_status(
                job_id=job_id,
                body=JobStatusEnvelope(
                    workerId=self._worker_id,
                    status="failed",
                    detail=str(error),
                    metrics={},
                ),
            )
            raise
        finally:
            self.on_task_end()

    def _register(self) -> None:
        body = WorkerRegistrationEnvelope(
            workerId=self._worker_id,
            node=NodeRegistrationBody(
                name=self._settings.node_name,
                sshAlias=self._settings.node_ssh_alias,
                hostname=self._settings.node_hostname or socket.gethostname(),
                gpuAvailable=self._gpu_info.available,
                gpuName=self._gpu_info.name,
                dockerVersion=self._settings.node_docker_version,
                nvidiaRuntimeVersion=self._settings.node_nvidia_runtime_version,
            ),
            worker=WorkerRegistrationBody(
                workerName=self._settings.worker_name,
                queueNames=self._settings.worker_queues,
                capacitySlots=self._settings.worker_capacity_slots,
                supportsFace=self._settings.face_enabled,
                supportsTextEmbedding=self._settings.embedding_enabled,
                supportsImageEmbedding=self._settings.embedding_enabled,
                supportsGpu=self._gpu_configured,
                detectorModel=self._settings.detector_model_name,
                embeddingModel=self._settings.embedding_model_name,
                faceModel=self._settings.face_model_name if self._settings.face_enabled else None,
            ),
        )
        response = self._http.post(self._settings.register_url, json=body.model_dump(mode="json"))
        response.raise_for_status()
        with self._state_lock:
            self._state.registered = True
            self._state.last_error = None

    def _heartbeat_loop(self) -> None:
        while not self._stop_event.wait(self._settings.worker_heartbeat_interval_seconds):
            try:
                with self._state_lock:
                    active_jobs = self._state.active_jobs
                gpu_percent, gpu_memory_percent = self._read_gpu_stats()
                body = WorkerHeartbeatEnvelope(
                    workerId=self._worker_id,
                    status="healthy",
                    activeJobs=active_jobs,
                    queueDepthHint=0,
                    runtime=WorkerHeartbeatRuntime(
                        cpuPercent=psutil.cpu_percent(interval=None),
                        memoryPercent=psutil.virtual_memory().percent,
                        gpuPercent=gpu_percent,
                        gpuMemoryPercent=gpu_memory_percent,
                    ),
                    checkedAt=utcnow_iso(),
                )
                response = self._http.post(
                    self._settings.heartbeat_url,
                    json=body.model_dump(mode="json"),
                )
                response.raise_for_status()
                with self._state_lock:
                    self._state.last_error = None
            except Exception as error:  # pragma: no cover - runtime integration branch
                LOGGER.warning("Worker heartbeat failed: %s", error)
                with self._state_lock:
                    self._state.last_error = str(error)

    def _read_gpu_stats(self) -> tuple[float | None, float | None]:
        if not self._gpu_info.available:
            return None, None
        try:
            completed = subprocess.run(
                [
                    "nvidia-smi",
                    "--query-gpu=utilization.gpu,memory.used,memory.total",
                    "--format=csv,noheader,nounits",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            line = completed.stdout.strip().splitlines()[0]
            gpu_util_s, mem_used_s, mem_total_s = [part.strip() for part in line.split(",")]
            mem_total = float(mem_total_s)
            gpu_memory_percent = (float(mem_used_s) / mem_total) * 100.0 if mem_total > 0 else None
            return float(gpu_util_s), gpu_memory_percent
        except Exception:
            return None, None

    def _run_segment(self, task_payload: dict[str, Any]) -> dict[str, object]:
        sample_fps = float(task_payload["pipeline"]["sampleFps"])
        local_segment_path = str(task_payload["segment"].get("localPath") or "")
        with TemporaryDirectory(dir=self._settings.worker_runtime_dir) as temp_dir:
            downloaded_path = str(Path(temp_dir) / Path(task_payload["segment"]["objectKey"]).name)
            self._object_store.download_file(
                bucket_name=str(task_payload["segment"]["bucket"]),
                object_key=str(task_payload["segment"]["objectKey"]),
                file_path=downloaded_path,
            )
            source = VisionSource(
                id=str(task_payload["sourceId"]),
                site_id=str(task_payload["siteId"]),
                camera_id=str(task_payload["cameraId"]),
                camera_name=str(task_payload["cameraName"]),
                path_name=str(task_payload["cameraId"]),
                stream_url="",
                live_stream_url=None,
                capture_mode="recording-segment",
            )
            processed = self._processor.process_segment(
                job_id=str(task_payload["jobId"]),
                source=source,
                sample_fps=sample_fps,
                segment_path=downloaded_path,
                segment_start_at=str(task_payload["segment"]["segmentStartAt"]),
            )
        serialized_bundles = [
            self._serialize_bundle(bundle, local_segment_path=local_segment_path)
            for bundle in processed.track_bundles
        ]
        return {
            "jobId": str(task_payload["jobId"]),
            "trackCount": len(serialized_bundles),
            "durationSec": processed.duration_sec,
            "bundles": serialized_bundles,
            "metrics": {
                "framesDecoded": processed.metrics.frames_decoded,
                "framesSampled": processed.metrics.frames_sampled,
                "tracksClosed": processed.metrics.tracks_closed,
                "durationMs": processed.metrics.duration_ms,
            },
        }

    def _serialize_bundle(
        self,
        bundle: PreparedTrackBundle,
        *,
        local_segment_path: str,
    ) -> TrackBundleBody:
        track_row = dict(bundle.track_row)
        if local_segment_path:
            track_row["segment_path"] = local_segment_path
        return TrackBundleBody(
            trackRow=track_row,
            artifacts=[
                TrackArtifactBody(
                    role=artifact.role,
                    kind=artifact.kind,
                    mimeType=artifact.mime_type,
                    payloadBase64=base64.b64encode(artifact.payload).decode("ascii"),
                )
                for artifact in bundle.artifacts
            ],
            embedding=bundle.embedding,
            faceEmbedding=bundle.face_embedding,
        )

    def _post_job_results(
        self,
        *,
        job_id: str,
        bundles: list[TrackBundleBody],
        duration_sec: float,
    ) -> None:
        envelope = JobResultsEnvelope(
            workerId=self._worker_id,
            durationSec=duration_sec,
            trackBundles=bundles,
        )
        response = self._http.post(
            f"{self._settings.job_results_base_url.rstrip('/')}/api/v1/internal/vision/jobs/{job_id}/results",
            json=envelope.model_dump(mode="json"),
        )
        response.raise_for_status()

    def _post_job_status(self, *, job_id: str, body: JobStatusEnvelope) -> None:
        response = self._http.post(
            f"{self._settings.job_status_base_url.rstrip('/')}/api/v1/internal/vision/jobs/{job_id}/status",
            json=body.model_dump(mode="json"),
        )
        response.raise_for_status()


def _build_runtime() -> DistributedWorkerRuntime:
    settings = get_settings()
    return DistributedWorkerRuntime(settings)


runtime = _build_runtime()
celery_app = Celery(
    "qaongdur-vision-worker",
    broker=get_settings().queue_broker_url,
    backend=get_settings().queue_result_backend,
)


@celery_app.task(name="vision.process_segment")
def process_segment(task_payload: dict[str, Any]) -> dict[str, object]:
    return runtime.process_segment_task(task_payload)


def run() -> None:
    logging.basicConfig(level=logging.INFO)
    runtime.start()
    try:
        celery_app.worker_main(
            [
                "worker",
                "--loglevel=INFO",
                "--pool=solo",
                "--hostname",
                f"{runtime.worker_id}@{get_settings().node_name}",
                "-Q",
                ",".join(get_settings().worker_queues),
            ]
        )
    finally:
        runtime.stop()


if __name__ == "__main__":
    run()
