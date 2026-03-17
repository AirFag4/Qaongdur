from __future__ import annotations

from dataclasses import dataclass
import importlib
import logging
from threading import Lock

import cv2
import numpy as np

LOGGER = logging.getLogger(__name__)


def _resolve_runtime_device(
    requested_device: str,
    *,
    torch_module: object,
) -> tuple[str, str | None]:
    normalized = requested_device.strip().lower() if requested_device else "cpu"
    has_cuda = bool(getattr(torch_module.cuda, "is_available")())

    if normalized == "auto":
        if has_cuda:
            return "cuda:0", None
        return "cpu", "CUDA unavailable; falling back to CPU."

    if normalized.startswith("cuda") and not has_cuda:
        return "cpu", f"Requested {normalized} but CUDA is unavailable; falling back to CPU."

    return normalized or "cpu", None


@dataclass(slots=True)
class EmbeddingResult:
    status: str
    model_name: str
    vector: list[float]


class CropEmbedder:
    def __init__(self, *, enabled: bool, model_name: str, device: str) -> None:
        self._enabled = enabled
        self._model_name = model_name
        self._requested_device = device
        self._runtime_device = "cpu"
        self._model = None
        self._preprocess = None
        self._tokenizer = None
        self._torch = None
        self._Image = None
        self._init_lock = Lock()
        self.runtime_model_name = model_name if enabled else "histogram-fallback"
        self.runtime_state = "pending" if enabled else "disabled"
        self.runtime_detail = (
            f"{model_name} will initialize on first embedding request."
            if enabled
            else "Embedding stage disabled by configuration."
        )

    def embed(self, crop_bgr: np.ndarray) -> EmbeddingResult:
        if (
            not self._ensure_runtime()
            or self._model is None
            or self._preprocess is None
            or self._Image is None
            or self._torch is None
        ):
            histogram = self._histogram_embedding(crop_bgr)
            return EmbeddingResult(
                status="fallback",
                model_name=self.runtime_model_name,
                vector=histogram,
            )

        rgb_image = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2RGB)
        pil_image = self._Image.fromarray(rgb_image)
        tensor = self._preprocess(pil_image).unsqueeze(0).to(self._runtime_device)
        with self._torch.no_grad():
            features = self._model.encode_image(tensor)
            features = features / features.norm(dim=-1, keepdim=True)
        vector = features[0].cpu().numpy().astype(float).tolist()
        return EmbeddingResult(
            status="ready",
            model_name=self.runtime_model_name,
            vector=vector,
        )

    def embed_text(self, text: str) -> EmbeddingResult:
        normalized = text.strip()
        if not normalized:
            return EmbeddingResult(
                status="empty-text",
                model_name=self.runtime_model_name,
                vector=[],
            )
        if (
            not self._ensure_runtime()
            or self._model is None
            or self._tokenizer is None
            or self._torch is None
        ):
            return EmbeddingResult(
                status="text-unsupported",
                model_name=self.runtime_model_name,
                vector=[],
            )

        tokens = self._tokenizer([normalized])
        if hasattr(tokens, "to"):
            tokens = tokens.to(self._runtime_device)
        with self._torch.no_grad():
            features = self._model.encode_text(tokens)
            features = features / features.norm(dim=-1, keepdim=True)
        vector = features[0].cpu().numpy().astype(float).tolist()
        return EmbeddingResult(
            status="ready",
            model_name=self.runtime_model_name,
            vector=vector,
        )

    def _ensure_runtime(self) -> bool:
        if not self._enabled:
            self.runtime_model_name = "histogram-fallback"
            self.runtime_state = "disabled"
            self.runtime_detail = "Embedding stage disabled by configuration."
            return False
        if (
            self._model is not None
            and self._preprocess is not None
            and self._tokenizer is not None
            and self._Image is not None
            and self._torch is not None
        ):
            return True
        if self.runtime_state == "fallback":
            return False

        with self._init_lock:
            if (
                self._model is not None
                and self._preprocess is not None
                and self._tokenizer is not None
                and self._Image is not None
                and self._torch is not None
            ):
                return True
            if self.runtime_state == "fallback":
                return False

            self.runtime_state = "initializing"
            self.runtime_detail = f"Loading {self._model_name} on first embedding request."
            try:
                open_clip = importlib.import_module("open_clip")
                torch = importlib.import_module("torch")
                image_module = importlib.import_module("PIL.Image")

                self._runtime_device, fallback_detail = _resolve_runtime_device(
                    self._requested_device,
                    torch_module=torch,
                )
                if self._runtime_device == "cpu":
                    torch.set_num_threads(1)
                model, _, preprocess = open_clip.create_model_and_transforms(
                    self._model_name,
                    pretrained="dfndr2b",
                )
                model = model.to(self._runtime_device)
                model.eval()
                self._model = model
                self._preprocess = preprocess
                self._tokenizer = open_clip.get_tokenizer(self._model_name)
                self._torch = torch
                self._Image = image_module
                self.runtime_model_name = self._model_name
                self.runtime_state = "ready"
                self.runtime_detail = (
                    f"{self._model_name} ready for image and text embeddings on "
                    f"{self._runtime_device}."
                )
                if fallback_detail:
                    self.runtime_detail = f"{self.runtime_detail} {fallback_detail}"
                return True
            except Exception as error:  # pragma: no cover - runtime dependency branch
                LOGGER.warning("Falling back to histogram embedder: %s", error)
                self._model = None
                self._preprocess = None
                self._tokenizer = None
                self._torch = None
                self._Image = None
                self.runtime_model_name = "histogram-fallback"
                self.runtime_state = "fallback"
                self.runtime_detail = f"Histogram fallback active: {error}"
                return False

    def _histogram_embedding(self, crop_bgr: np.ndarray) -> list[float]:
        resized = cv2.resize(crop_bgr, (32, 32), interpolation=cv2.INTER_AREA)
        # Keep fallback vectors aligned with the Qdrant object-embedding collection schema.
        histogram = cv2.calcHist([resized], [0, 1, 2], None, [8, 8, 8], [0, 256] * 3)
        flattened = histogram.flatten().astype("float32")
        norm = float(np.linalg.norm(flattened))
        if norm > 0:
            flattened /= norm
        return flattened.astype(float).tolist()
