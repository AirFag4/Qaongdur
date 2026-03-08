from __future__ import annotations

from dataclasses import dataclass
import logging

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
    ) -> None:
        self._enabled = enabled
        self._model_name = model_name
        self._minimum_track_seconds = minimum_track_seconds
        self._session = None
        self._runtime_available = False

        if not enabled:
            return

        try:
            import inspireface as isf

            self._isf = isf
            self._runtime_available = True
        except Exception as error:  # pragma: no cover - runtime dependency branch
            LOGGER.warning("Face stage unavailable: %s", error)

    @property
    def runtime_model_name(self) -> str:
        return self._model_name

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
        if not self._runtime_available:
            return FaceEmbeddingResult(status="unavailable", model_name=self._model_name, vector=None)

        try:  # pragma: no cover - runtime dependency branch
            if self._session is None:
                self._isf.reload("Pikachu")
                self._session = self._isf.InspireFaceSession(
                    self._isf.HF_ENABLE_FACE_RECOGNITION,
                    self._isf.HF_DETECT_MODE_ALWAYS_DETECT,
                )
            faces = self._session.face_detection(crop_bgr)
            if not faces:
                return FaceEmbeddingResult(status="no-face", model_name=self._model_name, vector=None)
            feature = self._session.face_feature_extract(crop_bgr, faces[0])
            return FaceEmbeddingResult(
                status="ready",
                model_name=self._model_name,
                vector=np.asarray(feature, dtype=float).tolist(),
            )
        except Exception as error:  # pragma: no cover - runtime dependency branch
            LOGGER.warning("Face stage failed: %s", error)
            return FaceEmbeddingResult(status="error", model_name=self._model_name, vector=None)
