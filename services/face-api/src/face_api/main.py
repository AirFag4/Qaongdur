from __future__ import annotations

import base64
from datetime import UTC, datetime
from functools import lru_cache

import cv2
import numpy as np
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from .config import get_settings
from .runtime import FaceRuntime


class FaceEmbedRequest(BaseModel):
    imageBase64: str


def _encode_jpeg_base64(image_bgr: np.ndarray | None) -> str | None:
    if image_bgr is None:
        return None
    ok, encoded = cv2.imencode(".jpg", image_bgr)
    if not ok:
        return None
    return base64.b64encode(encoded.tobytes()).decode("ascii")


@lru_cache(maxsize=1)
def get_runtime() -> FaceRuntime:
    return FaceRuntime(get_settings())


def create_app() -> FastAPI:
    settings = get_settings()
    runtime = get_runtime()
    app = FastAPI(
        title="Qaongdur Face API",
        version="0.1.0",
        summary="InspireFace-backed crop embedding sidecar for Qaongdur vision.",
    )

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok", "service": "face-api"}

    @app.get("/readyz")
    async def readyz() -> dict[str, object]:
        status = runtime.status()
        return {
            "status": "ok",
            "service": "face-api",
            "available": status.available,
            "detail": status.detail,
            "checkedAt": datetime.now(tz=UTC).isoformat(),
        }

    @app.get("/api/v1/face/status")
    async def get_face_status() -> dict[str, object]:
        status = runtime.status()
        return {
            "available": status.available,
            "mode": status.mode,
            "modelName": status.model_name,
            "detail": status.detail,
        }

    @app.post("/api/v1/face/embed")
    async def embed_face(body: FaceEmbedRequest) -> dict[str, object]:
        try:
            image_bytes = base64.b64decode(body.imageBase64)
        except Exception as error:
            raise HTTPException(status_code=400, detail=f"Invalid base64 payload: {error}") from error

        image_array = np.frombuffer(image_bytes, dtype=np.uint8)
        image_bgr = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
        if image_bgr is None:
            raise HTTPException(status_code=400, detail="Unable to decode image bytes.")

        response = runtime.embed(image_bgr)
        return {
            "status": response.status,
            "modelName": response.model_name,
            "vector": response.vector,
            "detail": response.detail,
            "faceCount": response.face_count,
            "faceBox": response.face_bbox,
            "detectedFaceImageBase64": _encode_jpeg_base64(response.detected_face_bgr),
            "alignedFaceImageBase64": _encode_jpeg_base64(response.aligned_face_bgr),
        }

    return app


app = create_app()


def run() -> None:
    settings = get_settings()
    uvicorn.run(
        "face_api.main:app",
        host=settings.service_host,
        port=settings.service_port,
        reload=settings.env == "development",
    )


if __name__ == "__main__":
    run()
