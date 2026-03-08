from __future__ import annotations

from datetime import UTC, datetime
from functools import lru_cache

import uvicorn
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from .config import get_settings
from .demo_data import DEMO_PIPELINES
from .pipeline import VisionPipelineService


class DemoDetection(BaseModel):
    label: str
    confidence: float
    severity: str
    boundingBox: dict[str, int]


class DemoAlert(BaseModel):
    title: str
    rule: str
    severity: str


class DemoInferenceResult(BaseModel):
    sourceId: str
    siteId: str
    cameraId: str
    summary: str
    detections: list[DemoDetection]
    recommendedAlert: DemoAlert
    capturedAt: str


class DemoRunRequest(BaseModel):
    sourceId: str = Field(
        default="demo-loading-dock",
        description="Seeded demo source configured inside the vision scaffold.",
    )


class MockJobRunRequest(BaseModel):
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
        summary="Demo-ready vision pipeline scaffold for Qaongdur",
    )

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok", "service": "vision"}

    @app.get("/readyz")
    async def readyz() -> dict[str, object]:
        return {
            "status": "ok",
            "service": "vision",
            "sampleMode": settings.sample_mode,
            "checkedAt": datetime.now(tz=UTC).isoformat(),
        }

    @app.get("/api/v1/vision/mock-sources")
    async def list_mock_sources() -> dict[str, object]:
        return {
            "count": len(pipeline.list_sources()),
            "sources": pipeline.list_sources(),
        }

    @app.get("/api/v1/vision/status")
    async def get_vision_status() -> dict[str, object]:
        return pipeline.get_status()

    @app.post("/api/v1/vision/mock-jobs/run")
    async def run_mock_job(body: MockJobRunRequest) -> dict[str, object]:
        if not settings.sample_mode:
            raise HTTPException(status_code=503, detail="Mock mode is disabled.")
        return pipeline.start_job(source_ids=body.sourceIds or None)

    @app.get("/api/v1/vision/crop-tracks")
    async def list_crop_tracks(
        sourceId: str | None = None,
        label: str | None = Query(default=None, pattern="^(person|vehicle|all)?$"),
    ) -> dict[str, object]:
        tracks = pipeline.list_crop_tracks(source_id=sourceId, label=label)
        return {
            "count": len(tracks),
            "tracks": tracks,
        }

    @app.get("/api/v1/vision/pipelines")
    async def list_demo_pipelines() -> dict[str, object]:
        return {
            "sampleMode": settings.sample_mode,
            "count": len(DEMO_PIPELINES),
            "pipelines": DEMO_PIPELINES,
        }

    @app.post("/api/v1/vision/demo/run")
    async def run_demo_pipeline(body: DemoRunRequest) -> DemoInferenceResult:
        if not settings.sample_mode:
            raise HTTPException(status_code=503, detail="Demo mode is disabled.")

        for pipeline in DEMO_PIPELINES:
            if pipeline["sourceId"] == body.sourceId:
                return DemoInferenceResult(**pipeline)

        raise HTTPException(status_code=404, detail="Unknown demo source.")

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
