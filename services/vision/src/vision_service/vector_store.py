from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any
from uuid import NAMESPACE_URL, uuid4, uuid5

import httpx

LOGGER = logging.getLogger(__name__)


def _qdrant_point_id(point_id: str | None) -> str:
    seed = point_id or uuid4().hex
    return str(uuid5(NAMESPACE_URL, seed))


@dataclass(slots=True)
class VectorStoreStatus:
    enabled: bool
    available: bool
    provider: str
    detail: str


class QdrantVectorStore:
    def __init__(
        self,
        *,
        enabled: bool,
        base_url: str,
        object_collection: str,
        face_collection: str,
        timeout_seconds: float,
    ) -> None:
        self._enabled = enabled
        self._base_url = base_url.rstrip("/")
        self._object_collection = object_collection
        self._face_collection = face_collection
        self._timeout_seconds = timeout_seconds
        self._collection_sizes: dict[str, int] = {}
        self._status = VectorStoreStatus(
            enabled=enabled,
            available=False,
            provider="qdrant",
            detail=(
                "Vector store disabled by configuration."
                if not enabled
                else "Vector store has not been contacted yet."
            ),
        )

    @property
    def status(self) -> VectorStoreStatus:
        return self._status

    def upsert_object_embedding(
        self,
        *,
        track_id: str,
        camera_id: str,
        label: str,
        captured_at: str,
        vector: list[float],
    ) -> None:
        self._upsert_vector(
            collection=self._object_collection,
            point_id=track_id,
            vector=vector,
            payload={
                "trackId": track_id,
                "cameraId": camera_id,
                "label": label,
                "capturedAt": captured_at,
                "embeddingKind": "object",
            },
        )

    def upsert_face_embedding(
        self,
        *,
        track_id: str,
        camera_id: str,
        captured_at: str,
        vector: list[float],
    ) -> None:
        self._upsert_vector(
            collection=self._face_collection,
            point_id=f"{track_id}-face",
            vector=vector,
            payload={
                "trackId": track_id,
                "cameraId": camera_id,
                "capturedAt": captured_at,
                "embeddingKind": "face",
            },
        )

    def _upsert_vector(
        self,
        *,
        collection: str,
        point_id: str,
        vector: list[float],
        payload: dict[str, Any],
    ) -> None:
        if not self._enabled or not vector or not self._base_url:
            return
        try:
            self._ensure_collection(collection=collection, size=len(vector))
            with httpx.Client(timeout=self._timeout_seconds) as client:
                response = client.put(
                    f"{self._base_url}/collections/{collection}/points",
                    params={"wait": "true"},
                    json={
                        "points": [
                            {
                                "id": _qdrant_point_id(point_id),
                                "vector": [float(value) for value in vector],
                                "payload": {
                                    key: value
                                    for key, value in payload.items()
                                    if value is not None
                                },
                            }
                        ]
                    },
                )
                if not response.is_success:
                    detail = response.text.strip() or "unknown error"
                    raise httpx.HTTPStatusError(
                        f"{response.status_code} {response.reason_phrase}: {detail}",
                        request=response.request,
                        response=response,
                    )
        except httpx.HTTPError as error:
            LOGGER.warning("Qdrant upsert failed: %s", error)
            self._status = VectorStoreStatus(
                enabled=self._enabled,
                available=False,
                provider="qdrant",
                detail=f"Vector upsert failed: {error}",
            )
            return

        self._status = VectorStoreStatus(
            enabled=self._enabled,
            available=True,
            provider="qdrant",
            detail=f"Vectors are stored in collections {self._object_collection} and {self._face_collection}.",
        )

    def _ensure_collection(self, *, collection: str, size: int) -> None:
        if self._collection_sizes.get(collection) == size:
            return
        with httpx.Client(timeout=self._timeout_seconds) as client:
            response = client.put(
                f"{self._base_url}/collections/{collection}",
                json={
                    "vectors": {
                        "size": size,
                        "distance": "Cosine",
                    }
                },
            )
            if response.status_code == 409:
                existing = client.get(f"{self._base_url}/collections/{collection}")
                existing.raise_for_status()
                existing_size = (
                    existing.json()
                    .get("result", {})
                    .get("config", {})
                    .get("params", {})
                    .get("vectors", {})
                    .get("size")
                )
                if existing_size not in (None, size):
                    raise httpx.HTTPStatusError(
                        (
                            f"409 Conflict: collection {collection} exists with vector size "
                            f"{existing_size}, expected {size}"
                        ),
                        request=response.request,
                        response=response,
                    )
            else:
                response.raise_for_status()
        self._collection_sizes[collection] = size
        self._status = VectorStoreStatus(
            enabled=self._enabled,
            available=True,
            provider="qdrant",
            detail=f"Connected to {self._base_url}.",
        )
