from __future__ import annotations

from datetime import UTC, datetime

import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .config import get_settings
from .demo_data import DEMO_PIPELINES


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


def create_app() -> FastAPI:
    settings = get_settings()
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
