from __future__ import annotations

import uuid

from vision_service.vector_store import QdrantVectorStore


class _FakeResponse:
    def __init__(
        self,
        *,
        request_url: str,
        payload: dict[str, object],
        status_code: int = 200,
        body: dict[str, object] | None = None,
    ) -> None:
        self.request = type("Request", (), {"url": request_url})()
        self.status_code = status_code
        self.reason_phrase = "OK" if status_code < 400 else "Conflict"
        self.is_success = status_code < 400
        self._payload = payload
        self._body = body or {}
        self.text = "" if status_code < 400 else "conflict"

    def raise_for_status(self) -> None:
        if not self.is_success:
            raise RuntimeError(f"{self.status_code} {self.reason_phrase}")

    def json(self) -> dict[str, object]:
        return self._body


class _FakeClient:
    def __init__(
        self,
        sink: list[dict[str, object]],
        *,
        put_status_code: int = 200,
        existing_vector_size: int | None = None,
        **_: object,
    ) -> None:
        self._sink = sink
        self._put_status_code = put_status_code
        self._existing_vector_size = existing_vector_size

    def __enter__(self) -> "_FakeClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def put(
        self,
        url: str,
        *,
        params: dict[str, str] | None = None,
        json: dict[str, object] | None = None,
    ) -> _FakeResponse:
        payload = {
            "url": url,
            "params": params or {},
            "json": json or {},
        }
        self._sink.append(payload)
        return _FakeResponse(
            request_url=url,
            payload=payload,
            status_code=self._put_status_code,
        )

    def get(self, url: str) -> _FakeResponse:
        payload = {"url": url, "method": "GET"}
        self._sink.append(payload)
        return _FakeResponse(
            request_url=url,
            payload=payload,
            body={
                "result": {
                    "config": {
                        "params": {
                            "vectors": {
                                "size": self._existing_vector_size,
                            }
                        }
                    }
                }
            },
        )


def test_qdrant_upsert_normalizes_point_ids_and_waits(monkeypatch) -> None:
    calls: list[dict[str, object]] = []
    monkeypatch.setattr("vision_service.vector_store.httpx.Client", lambda **kwargs: _FakeClient(calls, **kwargs))

    store = QdrantVectorStore(
        enabled=True,
        base_url="http://qdrant:6333",
        object_collection="objects",
        face_collection="faces",
        timeout_seconds=5.0,
    )

    store.upsert_object_embedding(
        track_id="trk-camera-01",
        camera_id="cam-01",
        label="person",
        captured_at="2026-03-09T10:00:00+00:00",
        vector=[0.1, 0.2, 0.3],
    )

    assert len(calls) == 2
    collection_call, upsert_call = calls
    assert collection_call["url"] == "http://qdrant:6333/collections/objects"
    assert upsert_call["url"] == "http://qdrant:6333/collections/objects/points"
    assert upsert_call["params"] == {"wait": "true"}

    point = upsert_call["json"]["points"][0]
    assert point["payload"]["trackId"] == "trk-camera-01"
    assert point["payload"]["cameraId"] == "cam-01"
    assert point["vector"] == [0.1, 0.2, 0.3]
    assert str(uuid.UUID(point["id"])) == point["id"]


def test_qdrant_upsert_accepts_existing_collection_on_409(monkeypatch) -> None:
    calls: list[dict[str, object]] = []
    monkeypatch.setattr(
        "vision_service.vector_store.httpx.Client",
        lambda **kwargs: _FakeClient(
            calls,
            put_status_code=409,
            existing_vector_size=3,
            **kwargs,
        ),
    )

    store = QdrantVectorStore(
        enabled=True,
        base_url="http://qdrant:6333",
        object_collection="objects",
        face_collection="faces",
        timeout_seconds=5.0,
    )

    store.upsert_object_embedding(
        track_id="trk-camera-01",
        camera_id="cam-01",
        label="person",
        captured_at="2026-03-09T10:00:00+00:00",
        vector=[0.1, 0.2, 0.3],
    )

    assert store.status.available is True
    assert calls[1]["method"] == "GET"
