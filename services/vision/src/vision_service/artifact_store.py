from __future__ import annotations

from base64 import b64encode
from pathlib import Path

import cv2
import numpy as np


class ArtifactStore:
    def __init__(
        self,
        *,
        artifacts_dir: str,
        crop_jpeg_quality: int,
        crop_max_dimension: int,
    ) -> None:
        self._root = Path(artifacts_dir)
        self._root.mkdir(parents=True, exist_ok=True)
        self._jpeg_quality = crop_jpeg_quality
        self._crop_max_dimension = crop_max_dimension

    def encode_crop(self, crop_bgr: np.ndarray) -> bytes:
        image = self._resize_crop(crop_bgr)
        ok, buffer = cv2.imencode(
            ".jpg",
            image,
            [int(cv2.IMWRITE_JPEG_QUALITY), self._jpeg_quality],
        )
        if not ok:
            raise RuntimeError("Failed to encode crop artifact.")
        return bytes(buffer)

    def write_bytes(self, relative_path: str, payload: bytes) -> str:
        target = self._root / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
        return relative_path

    def delete_relative_path(self, relative_path: str) -> None:
        target = self._root / relative_path
        if target.exists():
            target.unlink()

    def read_as_data_url(self, relative_path: str) -> str:
        payload = (self._root / relative_path).read_bytes()
        return f"data:image/jpeg;base64,{b64encode(payload).decode('ascii')}"

    def _resize_crop(self, crop_bgr: np.ndarray) -> np.ndarray:
        height, width = crop_bgr.shape[:2]
        max_dim = max(height, width)
        if max_dim <= self._crop_max_dimension:
            return crop_bgr
        scale = self._crop_max_dimension / max_dim
        resized = cv2.resize(
            crop_bgr,
            (max(1, int(width * scale)), max(1, int(height * scale))),
            interpolation=cv2.INTER_AREA,
        )
        return resized
