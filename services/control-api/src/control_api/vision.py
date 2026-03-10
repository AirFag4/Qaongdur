from __future__ import annotations

import httpx
from fastapi import HTTPException, status

from .config import get_settings


class VisionServiceError(RuntimeError):
    pass


class VisionServiceClient:
    def __init__(self, *, base_url: str) -> None:
        self._base_url = base_url.rstrip("/")

    async def get_status(self) -> dict[str, object]:
        return await self._get_json("/api/v1/vision/status")

    async def list_sources(self) -> dict[str, object]:
        return await self._get_json("/api/v1/vision/sources")

    async def trigger_scan(self, *, source_ids: list[str]) -> dict[str, object]:
        return await self._post_json(
            "/api/v1/vision/scan",
            {"sourceIds": source_ids},
        )

    async def list_crop_tracks(
        self,
        *,
        source_id: str | None = None,
        camera_id: str | None = None,
        label: str | None = None,
        from_at: str | None = None,
        to_at: str | None = None,
        include_retired: bool = False,
        page: int | None = None,
        page_size: int | None = None,
    ) -> dict[str, object]:
        params = {}
        if source_id:
            params["sourceId"] = source_id
        if camera_id:
            params["cameraId"] = camera_id
        if label:
            params["label"] = label
        if from_at:
            params["fromAt"] = from_at
        if to_at:
            params["toAt"] = to_at
        if include_retired:
            params["includeRetired"] = "true"
        if page:
            params["page"] = str(page)
        if page_size:
            params["pageSize"] = str(page_size)
        return await self._get_json("/api/v1/vision/crop-tracks", params=params)

    async def get_crop_track(self, track_id: str) -> dict[str, object]:
        return await self._get_json(f"/api/v1/vision/crop-tracks/{track_id}")

    async def search_crop_tracks(
        self,
        *,
        source_id: str | None = None,
        camera_id: str | None = None,
        label: str | None = None,
        from_at: str | None = None,
        to_at: str | None = None,
        include_retired: bool = False,
        page: int | None = None,
        page_size: int | None = None,
        text_query: str | None = None,
        image_base64: str | None = None,
    ) -> dict[str, object]:
        payload: dict[str, object] = {}
        if source_id:
            payload["sourceId"] = source_id
        if camera_id:
            payload["cameraId"] = camera_id
        if label:
            payload["label"] = label
        if from_at:
            payload["fromAt"] = from_at
        if to_at:
            payload["toAt"] = to_at
        if include_retired:
            payload["includeRetired"] = True
        if page:
            payload["page"] = page
        if page_size:
            payload["pageSize"] = page_size
        if text_query:
            payload["textQuery"] = text_query
        if image_base64:
            payload["imageBase64"] = image_base64
        return await self._post_json("/api/v1/vision/crop-search", payload)

    async def _get_json(
        self,
        path: str,
        *,
        params: dict[str, str] | None = None,
    ) -> dict[str, object]:
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.get(f"{self._base_url}{path}", params=params)
        except httpx.HTTPError as error:
            raise VisionServiceError(str(error)) from error

        if not response.is_success:
            raise VisionServiceError(response.text.strip() or "Vision service request failed.")
        return response.json()

    async def _post_json(self, path: str, payload: dict[str, object]) -> dict[str, object]:
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.post(f"{self._base_url}{path}", json=payload)
        except httpx.HTTPError as error:
            raise VisionServiceError(str(error)) from error

        if not response.is_success:
            raise VisionServiceError(response.text.strip() or "Vision service request failed.")
        return response.json()


def get_vision_service_client() -> VisionServiceClient:
    settings = get_settings()
    return VisionServiceClient(base_url=settings.vision_service_url)


def raise_as_bad_gateway(error: VisionServiceError) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail=f"Vision service integration error: {error}",
    )
