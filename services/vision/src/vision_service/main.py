from __future__ import annotations

from datetime import UTC, datetime
from functools import lru_cache

import uvicorn
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from .config import get_settings
from .pipeline import VisionPipelineService


class SegmentScanRequest(BaseModel):
    sourceIds: list[str] = Field(default_factory=list)


@lru_cache(maxsize=1)
def get_pipeline_service() -> VisionPipelineService:
    return VisionPipelineService(get_settings())


def create_app() -> FastAPI:
    settings = get_settings()
    pipeline = get_pipeline_service()
    app = FastAPI(
        title="Qaongdur Vision Service",
        version="0.1.0",
        summary="Segment-driven vision pipeline for Qaongdur",
    )

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok", "service": "vision"}

    @app.get("/readyz")
    async def readyz() -> dict[str, object]:
        return {
            "status": "ok",
            "service": "vision",
            "autoIngest": True,
            "checkedAt": datetime.now(tz=UTC).isoformat(),
        }

    @app.get("/api/v1/vision/sources")
    async def list_sources() -> dict[str, object]:
        sources = pipeline.list_sources()
        return {
            "count": len(sources),
            "sources": sources,
        }

    @app.get("/api/v1/vision/mock-sources")
    async def list_sources_legacy() -> dict[str, object]:
        return await list_sources()

    @app.get("/api/v1/vision/status")
    async def get_vision_status() -> dict[str, object]:
        return pipeline.get_status()

    @app.post("/api/v1/vision/scan")
    async def run_segment_scan(body: SegmentScanRequest) -> dict[str, object]:
        del body
        return pipeline.start_job()

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
    ) -> dict[str, object]:
        tracks = pipeline.list_crop_tracks(
            source_id=sourceId,
            camera_id=cameraId,
            label=label,
            from_at=fromAt,
            to_at=toAt,
            include_retired=includeRetired,
        )
        return {
            "count": len(tracks),
            "tracks": tracks,
        }

    @app.get("/api/v1/vision/crop-tracks/{track_id}")
    async def get_crop_track(track_id: str) -> dict[str, object]:
        track = pipeline.get_crop_track(track_id)
        if track is None:
            raise HTTPException(status_code=404, detail=f"Track {track_id} was not found.")
        return track

    return app


app = create_app()


def run() -> None:
    settings = get_settings()
    uvicorn.run(
        "vision_service.main:app",
        host=settings.service_host,
        port=settings.service_port,
        reload=settings.env == "development",
    )


if __name__ == "__main__":
    run()
