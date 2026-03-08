from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path
from threading import Lock

import numpy as np

from .config import Settings

LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class FaceRuntimeStatus:
    available: bool
    mode: str
    model_name: str
    detail: str


@dataclass(slots=True)
class FaceEmbeddingResponse:
    status: str
    model_name: str
    vector: list[float] | None
    detail: str
    face_count: int


class FaceRuntime:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._lock = Lock()
        self._isf = None
        self._session = None
        self._runtime_error: str | None = None

    def status(self) -> FaceRuntimeStatus:
        self._ensure_session()
        if self._session is None:
            return FaceRuntimeStatus(
                available=False,
                mode="local-runtime",
                model_name=self._settings.model_name,
                detail=self._runtime_error or "InspireFace runtime is not ready.",
            )
        return FaceRuntimeStatus(
            available=True,
            mode="local-runtime",
            model_name=self._settings.model_name,
            detail=(
                "InspireFace runtime is ready with the "
                f"{self._settings.model_name} resource pack."
            ),
        )

    def embed(self, image_bgr: np.ndarray) -> FaceEmbeddingResponse:
        self._ensure_session()
        if self._session is None:
            return FaceEmbeddingResponse(
                status="service-not-ready",
                model_name=self._settings.model_name,
                vector=None,
                detail=self._runtime_error or "InspireFace runtime is not ready.",
                face_count=0,
            )

        try:
            faces = self._session.face_detection(image_bgr)
            if not faces:
                return FaceEmbeddingResponse(
                    status="no-face",
                    model_name=self._settings.model_name,
                    vector=None,
                    detail="No face was detected inside the provided crop.",
                    face_count=0,
                )
            feature = self._session.face_feature_extract(image_bgr, faces[0])
            return FaceEmbeddingResponse(
                status="ready",
                model_name=self._settings.model_name,
                vector=np.asarray(feature, dtype=float).tolist(),
                detail="Face embedding generated from the crop.",
                face_count=len(faces),
            )
        except Exception as error:  # pragma: no cover - runtime dependency branch
            LOGGER.warning("Face embedding failed: %s", error)
            return FaceEmbeddingResponse(
                status="error",
                model_name=self._settings.model_name,
                vector=None,
                detail=f"Face embedding failed: {error}",
                face_count=0,
            )

    def _ensure_session(self) -> None:
        if self._session is not None:
            return

        with self._lock:
            if self._session is not None:
                return

            bootstrap_error = self._read_bootstrap_error()
            if bootstrap_error:
                self._runtime_error = bootstrap_error
                return

            resource_path = Path(self._settings.resource_path)
            if not resource_path.exists():
                self._runtime_error = f"Resource pack was not found at {resource_path}."
                return

            try:
                import inspireface as isf
            except Exception as error:  # pragma: no cover - runtime dependency branch
                self._runtime_error = f"Unable to import inspireface: {error}"
                return

            try:  # pragma: no cover - runtime dependency branch
                if isf.query_launch_status():
                    isf.reload(self._settings.model_name, resource_path=str(resource_path))
                else:
                    isf.launch(self._settings.model_name, resource_path=str(resource_path))
                self._session = isf.InspireFaceSession(
                    isf.HF_ENABLE_FACE_RECOGNITION,
                    isf.HF_DETECT_MODE_ALWAYS_DETECT,
                )
                self._isf = isf
                self._runtime_error = None
            except Exception as error:
                self._runtime_error = f"Unable to initialize InspireFace: {error}"

    def _read_bootstrap_error(self) -> str | None:
        path = Path(self._settings.bootstrap_error_file)
        if not path.exists():
            return None
        text = path.read_text(encoding="utf-8").strip()
        return text or None
