from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path
from threading import Lock

import cv2
import numpy as np

from .config import Settings

LOGGER = logging.getLogger(__name__)
ARCFACE_TEMPLATE = np.asarray(
    [
        [38.2946, 51.6963],
        [73.5318, 51.5014],
        [56.0252, 71.7366],
        [41.5493, 92.3655],
        [70.7299, 92.2041],
    ],
    dtype=np.float32,
)
ALIGNED_FACE_SIZE = (112, 112)


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
    face_bbox: tuple[int, int, int, int] | None = None
    detected_face_bgr: np.ndarray | None = None
    aligned_face_bgr: np.ndarray | None = None


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
            selected_face = self._select_primary_face(faces)
            face_bbox = tuple(int(value) for value in selected_face.location)
            detected_face_bgr = self._extract_padded_face(image_bgr, face_bbox)
            aligned_face_bgr = self._align_face(image_bgr, selected_face)
            feature = self._session.face_feature_extract(image_bgr, selected_face)
            detail = "Face embedding generated from the selected face."
            if len(faces) > 1:
                detail = (
                    "Face embedding generated from the strongest detected face "
                    f"out of {len(faces)} faces."
                )
            return FaceEmbeddingResponse(
                status="ready",
                model_name=self._settings.model_name,
                vector=np.asarray(feature, dtype=float).tolist(),
                detail=detail,
                face_count=len(faces),
                face_bbox=face_bbox,
                detected_face_bgr=detected_face_bgr,
                aligned_face_bgr=aligned_face_bgr,
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

    def _select_primary_face(self, faces: list[object]) -> object:
        def face_score(face: object) -> tuple[float, float]:
            x1, y1, x2, y2 = getattr(face, "location")
            area = float(max(x2 - x1, 1) * max(y2 - y1, 1))
            confidence = float(getattr(face, "detection_confidence", 0.0))
            return (area, confidence)

        return max(faces, key=face_score)

    def _extract_padded_face(
        self,
        image_bgr: np.ndarray,
        face_bbox: tuple[int, int, int, int],
    ) -> np.ndarray:
        image_height, image_width = image_bgr.shape[:2]
        x1, y1, x2, y2 = face_bbox
        bbox_width = max(x2 - x1, 1)
        bbox_height = max(y2 - y1, 1)
        side = int(round(max(bbox_width, bbox_height) * 1.6))
        side = max(side, max(bbox_width, bbox_height))
        center_x = (x1 + x2) / 2.0
        center_y = (y1 + y2) / 2.0
        crop_x1 = int(round(center_x - side / 2.0))
        crop_y1 = int(round(center_y - side / 2.0))
        crop_x2 = crop_x1 + side
        crop_y2 = crop_y1 + side

        if crop_x1 < 0:
            crop_x2 = min(image_width, crop_x2 - crop_x1)
            crop_x1 = 0
        if crop_y1 < 0:
            crop_y2 = min(image_height, crop_y2 - crop_y1)
            crop_y1 = 0
        if crop_x2 > image_width:
            shift = crop_x2 - image_width
            crop_x1 = max(0, crop_x1 - shift)
            crop_x2 = image_width
        if crop_y2 > image_height:
            shift = crop_y2 - image_height
            crop_y1 = max(0, crop_y1 - shift)
            crop_y2 = image_height

        crop_x2 = max(crop_x1 + 1, crop_x2)
        crop_y2 = max(crop_y1 + 1, crop_y2)
        return image_bgr[crop_y1:crop_y2, crop_x1:crop_x2].copy()

    def _align_face(self, image_bgr: np.ndarray, face: object) -> np.ndarray | None:
        try:
            face_points = self._session.get_face_five_key_points(face).astype(np.float32)
        except Exception as error:  # pragma: no cover - runtime dependency branch
            LOGGER.warning("Face landmark extraction failed: %s", error)
            return None

        if face_points.shape != ARCFACE_TEMPLATE.shape:
            return None

        transform, _ = cv2.estimateAffinePartial2D(
            face_points,
            ARCFACE_TEMPLATE,
            method=cv2.LMEDS,
        )
        if transform is None:
            return None

        return cv2.warpAffine(
            image_bgr,
            transform,
            ALIGNED_FACE_SIZE,
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_REFLECT101,
        )
