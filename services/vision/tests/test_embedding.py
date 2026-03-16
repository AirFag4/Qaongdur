from __future__ import annotations

from contextlib import nullcontext
from unittest.mock import patch

import numpy as np

from vision_service.embedding import CropEmbedder


def test_histogram_fallback_stays_512d() -> None:
    embedder = CropEmbedder(enabled=False, model_name="MobileCLIP2-S0")

    crop = np.zeros((64, 64, 3), dtype=np.uint8)
    result = embedder.embed(crop)

    assert result.status == "fallback"
    assert result.model_name == "histogram-fallback"
    assert len(result.vector) == 512
    assert embedder.runtime_state == "disabled"


class _FakeFeatureRow:
    def __init__(self, values: np.ndarray) -> None:
        self._values = values

    def cpu(self) -> "_FakeFeatureRow":
        return self

    def numpy(self) -> np.ndarray:
        return self._values


class _FakeFeatureBatch:
    def __init__(self, values: list[list[float]] | np.ndarray) -> None:
        self._values = np.asarray(values, dtype=np.float32)

    def norm(self, dim: int = -1, keepdim: bool = True) -> "_FakeFeatureBatch":
        return _FakeFeatureBatch(
            np.linalg.norm(self._values, axis=dim, keepdims=keepdim),
        )

    def __truediv__(self, other: "_FakeFeatureBatch") -> "_FakeFeatureBatch":
        return _FakeFeatureBatch(self._values / other._values)

    def __getitem__(self, index: int) -> _FakeFeatureRow:
        return _FakeFeatureRow(self._values[index])


class _FakePreprocessOutput:
    def unsqueeze(self, dim: int) -> "_FakePreprocessOutput":
        del dim
        return self


class _FakeModel:
    def eval(self) -> "_FakeModel":
        return self

    def encode_image(self, tensor: _FakePreprocessOutput) -> _FakeFeatureBatch:
        del tensor
        return _FakeFeatureBatch([[3.0, 4.0]])

    def encode_text(self, tokens: list[str]) -> _FakeFeatureBatch:
        del tokens
        return _FakeFeatureBatch([[0.0, 5.0]])


class _FakeOpenClip:
    @staticmethod
    def create_model_and_transforms(model_name: str, *, pretrained: str):
        assert model_name == "MobileCLIP2-S0"
        assert pretrained == "dfndr2b"
        return _FakeModel(), None, lambda image: _FakePreprocessOutput()

    @staticmethod
    def get_tokenizer(model_name: str):
        assert model_name == "MobileCLIP2-S0"
        return lambda texts: texts


class _FakeTorch:
    @staticmethod
    def set_num_threads(count: int) -> None:
        assert count == 1

    @staticmethod
    def no_grad():
        return nullcontext()


class _FakeImageModule:
    @staticmethod
    def fromarray(array: np.ndarray) -> np.ndarray:
        return array


def test_embedder_initializes_mobileclip_lazily_on_first_request() -> None:
    import_calls: list[str] = []

    def fake_import_module(name: str):
        import_calls.append(name)
        if name == "open_clip":
            return _FakeOpenClip
        if name == "torch":
            return _FakeTorch
        if name == "PIL.Image":
            return _FakeImageModule
        raise AssertionError(f"Unexpected import {name}")

    with patch("vision_service.embedding.importlib.import_module", side_effect=fake_import_module):
        embedder = CropEmbedder(enabled=True, model_name="MobileCLIP2-S0")

        assert import_calls == []
        assert embedder.runtime_state == "pending"
        assert embedder.runtime_model_name == "MobileCLIP2-S0"

        image_result = embedder.embed(np.zeros((32, 32, 3), dtype=np.uint8))
        text_result = embedder.embed_text("person")

    assert import_calls == ["open_clip", "torch", "PIL.Image"]
    assert image_result.status == "ready"
    assert image_result.model_name == "MobileCLIP2-S0"
    assert np.allclose(image_result.vector, [0.6, 0.8])
    assert text_result.status == "ready"
    assert np.allclose(text_result.vector, [0.0, 1.0])
    assert embedder.runtime_state == "ready"


def test_embedder_caches_histogram_fallback_after_first_failed_load() -> None:
    import_calls: list[str] = []

    def fake_import_module(name: str):
        import_calls.append(name)
        if name == "open_clip":
            raise ImportError("missing open_clip")
        raise AssertionError(f"Unexpected import {name}")

    with patch("vision_service.embedding.importlib.import_module", side_effect=fake_import_module):
        embedder = CropEmbedder(enabled=True, model_name="MobileCLIP2-S0")

        assert import_calls == []
        image_result = embedder.embed(np.zeros((32, 32, 3), dtype=np.uint8))
        text_result = embedder.embed_text("person")

    assert import_calls == ["open_clip"]
    assert image_result.status == "fallback"
    assert image_result.model_name == "histogram-fallback"
    assert len(image_result.vector) == 512
    assert text_result.status == "text-unsupported"
    assert text_result.model_name == "histogram-fallback"
    assert embedder.runtime_state == "fallback"
