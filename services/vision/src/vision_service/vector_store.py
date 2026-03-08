from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any
from uuid import uuid4

import httpx

LOGGER = logging.getLogger(__name__)


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
                    json={
                        "points": [
                            {
                                "id": point_id if point_id else uuid4().hex,
                                "vector": vector,
                                "payload": payload,
                            }
                        ]
                    },
                )
                response.raise_for_status()
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
            response.raise_for_status()
        self._collection_sizes[collection] = size
        self._status = VectorStoreStatus(
            enabled=self._enabled,
            available=True,
            provider="qdrant",
            detail=f"Connected to {self._base_url}.",
        )
