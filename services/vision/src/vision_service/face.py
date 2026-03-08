from __future__ import annotations

import base64
from dataclasses import dataclass
import logging
import time

import cv2
import httpx
import numpy as np

LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class FaceEmbeddingResult:
    status: str
    model_name: str
    vector: list[float] | None


class FaceEmbedder:
    def __init__(
        self,
        *,
        enabled: bool,
        model_name: str,
        minimum_track_seconds: float,
        service_url: str,
        request_timeout_seconds: float,
    ) -> None:
        self._enabled = enabled
        self._model_name = model_name
        self._minimum_track_seconds = minimum_track_seconds
        self._service_url = service_url.rstrip("/") if service_url else ""
        self._request_timeout_seconds = request_timeout_seconds
        self._status_cache_ttl_seconds = 10.0
        self._last_probe_monotonic = 0.0
        self._runtime_available = False
        self._runtime_mode = "remote"
        self._runtime_state = "disabled" if not enabled else "unknown"
        self._runtime_detail = (
            "Face stage disabled by configuration."
            if not enabled
            else "Face runtime has not been probed yet."
        )

        if enabled:
            self._probe_runtime(force=True)

    @property
    def runtime_available(self) -> bool:
        self._probe_runtime()
        return self._runtime_available

    @property
    def runtime_mode(self) -> str:
        self._probe_runtime()
        return self._runtime_mode

    @property
    def runtime_model_name(self) -> str:
        self._probe_runtime()
        return self._model_name

    @property
    def runtime_detail(self) -> str:
        self._probe_runtime()
        return self._runtime_detail

    def maybe_embed(
        self,
        *,
        label: str,
        duration_seconds: float,
        crop_bgr: np.ndarray,
    ) -> FaceEmbeddingResult:
        if not self._enabled:
            return FaceEmbeddingResult(status="disabled", model_name=self._model_name, vector=None)
        if label != "person":
            return FaceEmbeddingResult(status="skipped-label", model_name=self._model_name, vector=None)
        if duration_seconds < self._minimum_track_seconds:
            return FaceEmbeddingResult(status="skipped-short-track", model_name=self._model_name, vector=None)

        self._probe_runtime(force=self._runtime_state != "ready")
        if self._runtime_state == "unreachable":
            return FaceEmbeddingResult(
                status="service-unreachable",
                model_name=self._model_name,
                vector=None,
            )
        if self._runtime_state != "ready":
            return FaceEmbeddingResult(
                status="service-not-ready",
                model_name=self._model_name,
                vector=None,
            )

        ok, encoded = cv2.imencode(".jpg", crop_bgr)
        if not ok:
            return FaceEmbeddingResult(status="encode-error", model_name=self._model_name, vector=None)

        payload = {
            "imageBase64": base64.b64encode(encoded.tobytes()).decode("ascii"),
        }

        try:
            with httpx.Client(timeout=self._request_timeout_seconds) as client:
                response = client.post(f"{self._service_url}/api/v1/face/embed", json=payload)
                response.raise_for_status()
            body = response.json()
        except httpx.HTTPError as error:
            LOGGER.warning("Face service call failed: %s", error)
            self._runtime_available = False
            self._runtime_state = "unreachable"
            self._runtime_detail = f"Face service call failed: {error}"
            return FaceEmbeddingResult(
                status="service-unreachable",
                model_name=self._model_name,
                vector=None,
            )

        model_name = str(body.get("modelName") or self._model_name)
        self._model_name = model_name
        return FaceEmbeddingResult(
            status=str(body.get("status") or "error"),
            model_name=model_name,
            vector=(
                [float(value) for value in body.get("vector", [])]
                if body.get("vector") is not None
                else None
            ),
        )

    def _probe_runtime(self, *, force: bool = False) -> None:
        if not self._enabled:
            self._runtime_available = False
            self._runtime_state = "disabled"
            self._runtime_mode = "remote"
            self._runtime_detail = "Face stage disabled by configuration."
            return
        if not self._service_url:
            self._runtime_available = False
            self._runtime_state = "not-configured"
            self._runtime_mode = "remote"
            self._runtime_detail = "Face service URL is not configured."
            return

        now = time.monotonic()
        if not force and now - self._last_probe_monotonic < self._status_cache_ttl_seconds:
            return

        try:
            with httpx.Client(timeout=self._request_timeout_seconds) as client:
                response = client.get(f"{self._service_url}/api/v1/face/status")
                response.raise_for_status()
            body = response.json()
        except httpx.HTTPError as error:
            LOGGER.warning("Unable to probe face service: %s", error)
            self._runtime_available = False
            self._runtime_state = "unreachable"
            self._runtime_mode = "remote"
            self._runtime_detail = f"Face service unreachable: {error}"
            self._last_probe_monotonic = now
            return

        self._runtime_available = bool(body.get("available"))
        self._runtime_state = "ready" if self._runtime_available else "not-ready"
        self._runtime_mode = str(body.get("mode") or "remote")
        self._runtime_detail = str(body.get("detail") or "Face runtime reported no detail.")
        self._model_name = str(body.get("modelName") or self._model_name)
        self._last_probe_monotonic = now
