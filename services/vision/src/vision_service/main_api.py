from __future__ import annotations

from datetime import UTC, datetime
from functools import lru_cache
from typing import Annotated

import uvicorn
from fastapi import Depends, FastAPI, Header, HTTPException, Query, status
from pydantic import BaseModel, Field

from .config import Settings, get_settings
from .distributed_models import (
    JobResultsEnvelope,
    JobStatusEnvelope,
    WorkerHeartbeatEnvelope,
    WorkerRegistrationEnvelope,
)
from .distributed_service import DistributedVisionService
from .pipeline import VisionPipelineService


class SegmentScanRequest(BaseModel):
    sourceIds: list[str] = Field(default_factory=list)


class CropSearchRequest(BaseModel):
    sourceId: str | None = None
    cameraId: str | None = None
    label: str | None = Field(default=None, pattern="^(person|vehicle|all)?$")
    fromAt: str | None = None
    toAt: str | None = None
    includeRetired: bool = False
    page: int = 1
    pageSize: int = 20
    textQuery: str | None = None
    imageBase64: str | None = None


def _require_internal_token(
    x_qaongdur_internal_token: Annotated[str | None, Header()] = None,
    settings: Annotated[Settings, Depends(get_settings)] = None,
) -> None:
    if not x_qaongdur_internal_token or x_qaongdur_internal_token != settings.internal_service_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid internal service token.",
        )


@lru_cache(maxsize=1)
def get_query_pipeline() -> VisionPipelineService:
    return VisionPipelineService(get_settings(), start_background_threads=False)


@lru_cache(maxsize=1)
def get_distributed_service() -> DistributedVisionService:
    return DistributedVisionService(
        settings=get_settings(),
        query_pipeline=get_query_pipeline(),
    )


def create_app() -> FastAPI:
    query_pipeline = get_query_pipeline()
    distributed = get_distributed_service()
    app = FastAPI(
        title="Qaongdur Vision API",
        version="0.2.0",
        summary="Distributed segment scheduler and query surface for Qaongdur",
    )

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok", "service": "vision-api"}

    @app.get("/readyz")
    async def readyz() -> dict[str, object]:
        return {
            "status": "ok",
            "service": "vision-api",
            "executionMode": "api",
            "checkedAt": datetime.now(tz=UTC).isoformat(),
        }

    @app.get("/api/v1/vision/sources")
    async def list_sources() -> dict[str, object]:
        sources = query_pipeline.list_sources()
        return {
            "count": len(sources),
            "sources": sources,
        }

    @app.get("/api/v1/vision/mock-sources")
    async def list_sources_legacy() -> dict[str, object]:
        return await list_sources()

    @app.get("/api/v1/vision/status")
    async def get_vision_status() -> dict[str, object]:
        return distributed.get_status()

    @app.post("/api/v1/vision/scan")
    async def run_segment_scan(body: SegmentScanRequest) -> dict[str, object]:
        del body
        return distributed.trigger_scan()

    @app.post("/api/v1/vision/mock-jobs/run")
    async def run_segment_scan_legacy(body: SegmentScanRequest) -> dict[str, object]:
        return await run_segment_scan(body)

    @app.get("/api/v1/vision/crop-tracks")
    async def list_crop_tracks(
        sourceId: str | None = None,
        cameraId: str | None = None,
        label: str | None = Query(default=None, pattern="^(person|vehicle|all)?$"),
        fromAt: str | None = None,
        toAt: str | None = None,
        includeRetired: bool = False,
        page: int = 1,
        pageSize: int = 20,
    ) -> dict[str, object]:
        return query_pipeline.list_crop_tracks(
            source_id=sourceId,
            camera_id=cameraId,
            label=label,
            from_at=fromAt,
            to_at=toAt,
            include_retired=includeRetired,
            page=page,
            page_size=pageSize,
        )

    @app.get("/api/v1/vision/crop-tracks/{track_id}")
    async def get_crop_track(track_id: str) -> dict[str, object]:
        track = query_pipeline.get_crop_track(track_id)
        if track is None:
            raise HTTPException(status_code=404, detail=f"Track {track_id} was not found.")
        return track

    @app.post("/api/v1/vision/crop-search")
    async def search_crop_tracks(body: CropSearchRequest) -> dict[str, object]:
        try:
            return query_pipeline.search_crop_tracks(
                text_query=body.textQuery,
                image_base64=body.imageBase64,
                source_id=body.sourceId,
                camera_id=body.cameraId,
                label=body.label,
                from_at=body.fromAt,
                to_at=body.toAt,
                include_retired=body.includeRetired,
                page=body.page,
                page_size=body.pageSize,
            )
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @app.get("/api/v1/analytics/workers")
    async def list_analytics_workers() -> dict[str, object]:
        return distributed.list_workers()

    @app.get("/api/v1/analytics/nodes")
    async def list_analytics_nodes() -> dict[str, object]:
        return distributed.list_nodes()

    @app.get("/api/v1/analytics/queues")
    async def list_analytics_queues() -> dict[str, object]:
        return distributed.list_queues()

    @app.post("/api/v1/internal/analytics/workers/register")
    async def register_worker(
        body: WorkerRegistrationEnvelope,
        _: Annotated[None, Depends(_require_internal_token)],
    ) -> dict[str, object]:
        return distributed.register_worker(body)

    @app.post("/api/v1/internal/analytics/workers/heartbeat")
    async def heartbeat_worker(
        body: WorkerHeartbeatEnvelope,
        _: Annotated[None, Depends(_require_internal_token)],
    ) -> dict[str, object]:
        return distributed.heartbeat_worker(body)

    @app.post("/api/v1/internal/vision/jobs/{job_id}/status")
    async def update_job_status(
        job_id: str,
        body: JobStatusEnvelope,
        _: Annotated[None, Depends(_require_internal_token)],
    ) -> dict[str, object]:
        return distributed.update_job_status(job_id=job_id, body=body)

    @app.post("/api/v1/internal/vision/jobs/{job_id}/results")
    async def apply_job_results(
        job_id: str,
        body: JobResultsEnvelope,
        _: Annotated[None, Depends(_require_internal_token)],
    ) -> dict[str, object]:
        return distributed.apply_job_results(job_id=job_id, body=body)

    return app


app = create_app()


def run() -> None:
    settings = get_settings()
    uvicorn.run(
        "vision_service.main_api:app",
        host=settings.service_host,
        port=settings.service_port,
        reload=settings.env == "development",
    )


if __name__ == "__main__":
    run()
