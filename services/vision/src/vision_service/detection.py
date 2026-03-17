from __future__ import annotations

from dataclasses import dataclass
import logging

import numpy as np

from .domain import Detection

LOGGER = logging.getLogger(__name__)

CLASS_MAP = {
    0: ("person", "person"),
    2: ("vehicle", "car"),
    3: ("vehicle", "motorcycle"),
    5: ("vehicle", "bus"),
    7: ("vehicle", "truck"),
}


def _resolve_runtime_device(requested_device: str) -> tuple[str, str | None]:
    normalized = requested_device.strip().lower() if requested_device else "cpu"
    try:
        import torch

        has_cuda = bool(torch.cuda.is_available())
    except Exception:
        has_cuda = False

    if normalized == "auto":
        if has_cuda:
            return "cuda:0", None
        return "cpu", "CUDA unavailable; falling back to CPU."

    if normalized.startswith("cuda") and not has_cuda:
        return "cpu", f"Requested {normalized} but CUDA is unavailable; falling back to CPU."

    return normalized or "cpu", None


@dataclass(slots=True)
class DetectorStatus:
    available: bool
    model_name: str
    detail: str


class ObjectDetector:
    def __init__(
        self,
        *,
        model_name: str,
        confidence_threshold: float,
        device: str,
    ) -> None:
        self._confidence_threshold = confidence_threshold
        self._model_name = model_name
        self._requested_device = device
        self._runtime_device = "cpu"
        self._model = None
        self.status = DetectorStatus(
            available=False,
            model_name=model_name,
            detail="Detector not initialized.",
        )

        try:
            from ultralytics import YOLO

            self._runtime_device, fallback_detail = _resolve_runtime_device(device)
            self._model = YOLO(model_name)
            detail = f"Ultralytics detector ready on {self._runtime_device}."
            if fallback_detail:
                detail = f"{detail} {fallback_detail}"
            self.status = DetectorStatus(
                available=True,
                model_name=model_name,
                detail=detail,
            )
        except Exception as error:  # pragma: no cover - runtime dependency branch
            LOGGER.warning("Falling back to empty detector: %s", error)
            self.status = DetectorStatus(
                available=False,
                model_name=model_name,
                detail=f"Detector unavailable: {error}",
            )

    def detect(self, frame_bgr: np.ndarray) -> list[Detection]:
        if self._model is None:
            return []

        results = self._model.predict(
            source=frame_bgr,
            classes=sorted(CLASS_MAP.keys()),
            conf=self._confidence_threshold,
            device=self._runtime_device,
            verbose=False,
        )
        if not results:
            return []

        result = results[0]
        boxes = getattr(result, "boxes", None)
        if boxes is None:
            return []

        detections: list[Detection] = []
        for xyxy, confidence, class_id in zip(
            boxes.xyxy.cpu().numpy(),
            boxes.conf.cpu().numpy(),
            boxes.cls.cpu().numpy(),
            strict=False,
        ):
            class_key = int(class_id)
            if class_key not in CLASS_MAP:
                continue
            normalized_label, detector_label = CLASS_MAP[class_key]
            x1, y1, x2, y2 = [int(value) for value in xyxy.tolist()]
            detections.append(
                Detection(
                    label=normalized_label,
                    detector_label=detector_label,
                    confidence=float(confidence),
                    x1=x1,
                    y1=y1,
                    x2=x2,
                    y2=y2,
                )
            )
        return detections
