from __future__ import annotations

from dataclasses import dataclass

import httpx

from .domain import VisionSource


class ControlApiError(RuntimeError):
    pass


@dataclass(slots=True)
class SourceCatalogClient:
    base_url: str
    internal_token: str
    timeout_seconds: float = 10.0

    def list_sources(self) -> list[VisionSource]:
        if not self.base_url:
            raise ControlApiError("Control API base URL is not configured.")
        if not self.internal_token:
            raise ControlApiError("Internal service token is not configured.")

        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.get(
                    f"{self.base_url.rstrip('/')}/api/v1/internal/vision/sources",
                    headers={"X-Qaongdur-Internal-Token": self.internal_token},
                )
                response.raise_for_status()
        except httpx.HTTPError as error:
            raise ControlApiError(str(error)) from error

        body = response.json()
        sources: list[VisionSource] = []
        for item in body.get("sources", []):
            sources.append(
                VisionSource(
                    id=str(item["id"]),
                    site_id=str(item["siteId"]),
                    camera_id=str(item["cameraId"]),
                    camera_name=str(item["cameraName"]),
                    path_name=str(item["pathName"]),
                    stream_url=str(item["relayRtspUrl"]),
                    live_stream_url=(
                        str(item["liveStreamUrl"]) if item.get("liveStreamUrl") else None
                    ),
                    capture_mode="recording-segment",
                    source_kind=str(item.get("sourceKind") or "rtsp"),
                    ingest_mode=str(item.get("ingestMode") or "pull"),
                    health=str(item.get("health") or "offline"),
                    file_path="",
                    duration_sec=0.0,
                    frame_width=0,
                    frame_height=0,
                    source_fps=0.0,
                )
            )
        return sources
