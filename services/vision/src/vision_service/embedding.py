from __future__ import annotations

from dataclasses import dataclass
import logging

import cv2
import numpy as np

LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class EmbeddingResult:
    status: str
    model_name: str
    vector: list[float]


class CropEmbedder:
    def __init__(self, *, enabled: bool, model_name: str) -> None:
        self._enabled = enabled
        self._model_name = model_name
        self._model = None
        self._preprocess = None
        self.runtime_model_name = "histogram-fallback"

        if not enabled:
            return

        try:
            import open_clip
            import torch
            from PIL import Image

            self._Image = Image
            torch.set_num_threads(1)
            model, _, preprocess = open_clip.create_model_and_transforms(
                model_name,
                pretrained="dfndr2b",
            )
            model.eval()
            self._model = model
            self._preprocess = preprocess
            self._torch = torch
            self.runtime_model_name = model_name
        except Exception as error:  # pragma: no cover - runtime dependency branch
            LOGGER.warning("Falling back to histogram embedder: %s", error)

    def embed(self, crop_bgr: np.ndarray) -> EmbeddingResult:
        if self._model is None or self._preprocess is None:
            histogram = self._histogram_embedding(crop_bgr)
            return EmbeddingResult(
                status="fallback",
                model_name=self.runtime_model_name,
                vector=histogram,
            )

        rgb_image = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2RGB)
        pil_image = self._Image.fromarray(rgb_image)
        tensor = self._preprocess(pil_image).unsqueeze(0)
        with self._torch.no_grad():
            features = self._model.encode_image(tensor)
            features = features / features.norm(dim=-1, keepdim=True)
        vector = features[0].cpu().numpy().astype(float).tolist()
        return EmbeddingResult(
            status="ready",
            model_name=self.runtime_model_name,
            vector=vector,
        )

    def _histogram_embedding(self, crop_bgr: np.ndarray) -> list[float]:
        resized = cv2.resize(crop_bgr, (32, 32), interpolation=cv2.INTER_AREA)
        histogram = cv2.calcHist([resized], [0, 1, 2], None, [4, 4, 4], [0, 256] * 3)
        flattened = histogram.flatten().astype("float32")
        norm = float(np.linalg.norm(flattened))
        if norm > 0:
            flattened /= norm
        return flattened.astype(float).tolist()
