from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Any
from urllib.parse import urlencode, urlsplit

import httpx
from fastapi import HTTPException, status

from .config import get_settings


class MediaMtxError(RuntimeError):
    pass


@dataclass(slots=True)
class PathState:
    name: str
    ready: bool
    available: bool
    online: bool
    ready_time: str | None
    online_time: str | None
    tracks: list[str]


@dataclass(slots=True)
class RecordingSpan:
    start: str
    duration: float
    playback_url: str


class MediaMtxClient:
    def __init__(
        self,
        *,
        api_url: str,
        api_user: str,
        api_password: str,
        hls_public_url: str,
        playback_internal_url: str,
        playback_public_url: str,
    ) -> None:
        self._api_url = api_url.rstrip("/")
        self._api_auth = (api_user, api_password)
        self._hls_public_url = hls_public_url.rstrip("/")
        self._playback_internal_url = playback_internal_url.rstrip("/")
        self._playback_public_url = playback_public_url.rstrip("/")

    async def add_camera_path(self, *, path_name: str, source: str) -> None:
        payload = {
            "source": source,
            "rtspTransport": "tcp",
        }

        async with httpx.AsyncClient(auth=self._api_auth, timeout=5.0) as client:
            response = await client.post(
                f"{self._api_url}/v3/config/paths/add/{path_name}",
                json=payload,
            )

        if response.is_success:
            return

        detail = response.text.strip() or "MediaMTX rejected the path configuration."
        raise MediaMtxError(detail)

    async def delete_camera_path(
        self,
        *,
        path_name: str,
        ignore_missing: bool = False,
    ) -> None:
        async with httpx.AsyncClient(auth=self._api_auth, timeout=5.0) as client:
            response = await client.delete(
                f"{self._api_url}/v3/config/paths/delete/{path_name}",
            )

        if response.is_success:
            return
        if ignore_missing and response.status_code == status.HTTP_404_NOT_FOUND:
            return

        detail = response.text.strip() or "MediaMTX rejected the path deletion request."
        raise MediaMtxError(detail)

    async def reconnect_camera_path(self, *, path_name: str, source: str) -> None:
        await self.delete_camera_path(path_name=path_name, ignore_missing=True)
        await self.add_camera_path(path_name=path_name, source=source)

    async def list_paths(self) -> dict[str, PathState]:
        async with httpx.AsyncClient(auth=self._api_auth, timeout=5.0) as client:
            response = await client.get(f"{self._api_url}/v3/paths/list")

        if not response.is_success:
            detail = response.text.strip() or "Unable to query MediaMTX paths."
            raise MediaMtxError(detail)

        items = response.json().get("items", [])
        return {
            item["name"]: PathState(
                name=item["name"],
                ready=item.get("ready", False),
                available=item.get("available", False),
                online=item.get("online", False),
                ready_time=item.get("readyTime"),
                online_time=item.get("onlineTime"),
                tracks=item.get("tracks", []),
            )
            for item in items
        }

    async def list_recordings(
        self,
        *,
        path_name: str,
        start: str,
        end: str,
    ) -> list[RecordingSpan]:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(
                f"{self._playback_internal_url}/list",
                params={
                    "path": path_name,
                    "start": start,
                    "end": end,
                },
            )

        if response.status_code == status.HTTP_404_NOT_FOUND:
            return []

        if not response.is_success:
            detail = response.text.strip() or "Unable to query MediaMTX recordings."
            raise MediaMtxError(detail)

        spans = response.json()
        return [
            RecordingSpan(
                start=item["start"],
                duration=float(item["duration"]),
                playback_url=self.build_playback_url(
                    path_name=path_name,
                    start=item["start"],
                    duration=float(item["duration"]),
                ),
            )
            for item in spans
        ]

    def build_hls_url(self, path_name: str) -> str:
        return f"{self._hls_public_url}/{path_name}/index.m3u8"

    def build_playback_url(self, *, path_name: str, start: str, duration: float) -> str:
        return f"{self._playback_public_url}/get?{urlencode({'path': path_name, 'start': start, 'duration': duration, 'format': 'mp4'})}"


def path_state_to_health(path_state: PathState | None) -> str:
    if path_state is None:
        return "offline"
    if path_state.ready:
        return "healthy"
    if path_state.available or path_state.online:
        return "warning"
    return "offline"


def filter_playback_spans(
    spans: list[RecordingSpan],
    *,
    is_path_live: bool,
    segment_duration_seconds: int,
) -> list[RecordingSpan]:
    if not is_path_live:
        return spans

    minimum_complete_duration = max(segment_duration_seconds - 1, 1)
    return [
        span for span in spans if span.duration >= minimum_complete_duration
    ]


def extract_host_label(url: str) -> str:
    parsed = urlsplit(url)
    return parsed.hostname or "unknown"


def raise_as_bad_gateway(error: MediaMtxError) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail=f"MediaMTX integration error: {error}",
    )


@lru_cache(maxsize=1)
def get_mediamtx_client() -> MediaMtxClient:
    settings = get_settings()
    return MediaMtxClient(
        api_url=settings.mediamtx_api_url,
        api_user=settings.mediamtx_api_user,
        api_password=settings.mediamtx_api_password,
        hls_public_url=settings.mediamtx_hls_public_url,
        playback_internal_url=settings.mediamtx_playback_internal_url,
        playback_public_url=settings.mediamtx_playback_public_url,
    )
