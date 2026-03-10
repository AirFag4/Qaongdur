from __future__ import annotations

import numpy as np

from vision_service.embedding import CropEmbedder


def test_histogram_fallback_stays_512d() -> None:
    embedder = CropEmbedder(enabled=False, model_name="MobileCLIP2-S0")

    crop = np.zeros((64, 64, 3), dtype=np.uint8)
    result = embedder.embed(crop)

    assert result.status == "fallback"
    assert result.model_name == "histogram-fallback"
    assert len(result.vector) == 512
