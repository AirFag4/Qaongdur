from __future__ import annotations

import asyncio
from datetime import UTC, datetime
import hashlib
from pathlib import Path
import re
from typing import Annotated, Literal

import uvicorn
from fastapi import Depends, FastAPI, Header, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .audit import audit_logger
from .auth import (
    KeycloakPrincipal,
    PlatformRole,
    get_current_principal,
    has_required_acr,
    require_roles,
)
from .camera_store import CameraRecord, CameraStore, get_camera_store
from .config import Settings, get_settings
from .mediamtx import (
    MediaMtxClient,
    MediaMtxError,
    PathState,
    RecordingSpan,
    extract_host_label,
    filter_playback_spans,
    get_mediamtx_client,
    path_state_to_health,
    raise_as_bad_gateway,
)
from .vision import (
    VisionServiceClient,
    VisionServiceError,
    get_vision_service_client,
    raise_as_bad_gateway as raise_vision_bad_gateway,
)


class AgentApprovalBody(BaseModel):
    action: str
    approvalPath: list[str] = Field(default_factory=list)
    rationale: str | None = None
    requiresStepUp: bool = False


class CameraCreateBody(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    siteId: str | None = None
    name: str = Field(min_length=1, max_length=120)
    zone: str = Field(min_length=1, max_length=120)
    rtspUrl: str = Field(min_length=1)
    rtspTransport: Literal["automatic", "udp", "multicast", "tcp"] = "automatic"
    rtspAnyPort: bool = False

    @field_validator("rtspUrl")
    @classmethod
    def _validate_rtsp_url(cls, value: str) -> str:
        lowered = value.strip().lower()
        if not lowered.startswith(("rtsp://", "rtsps://")):
            raise ValueError("rtspUrl must begin with rtsp:// or rtsps://")
        return value.strip()


class PlaybackSearchBody(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    cameraIds: list[str] = Field(default_factory=list)
    from_: str = Field(alias="from")
    to: str
    includeAlerts: bool = True


class VisionMockJobBody(BaseModel):
    sourceIds: list[str] = Field(default_factory=list)


ALL_PLATFORM_ROLES: tuple[PlatformRole, ...] = (
    "platform-admin",
    "site-admin",
    "operator",
    "reviewer",
    "viewer",
)

SUPPORTED_MOCK_VIDEO_SUFFIXES = {".mp4", ".webm", ".mkv", ".mov"}
LEGACY_MOCK_VIDEO_FILES = {"people-walking.mp4", "vehicles.mp4"}


def _serialize_principal(principal: KeycloakPrincipal) -> dict[str, object]:
    return {
        "id": principal.subject,
        "username": principal.username,
        "displayName": principal.display_name,
        "email": principal.email,
        "roles": sorted(principal.roles),
        "acr": principal.acr,
    }


def _serialize_site(settings: Settings) -> dict[str, str]:
    return {
        "id": settings.default_site_id,
        "name": settings.default_site_name,
        "code": settings.default_site_code,
        "region": settings.default_site_region,
    }


def _serialize_camera(
    record: CameraRecord,
    path_state: PathState | None,
    media_client: MediaMtxClient,
) -> dict[str, object]:
    health = path_state_to_health(path_state)
    tags = ["mediamtx", "recording-enabled"]
    if record.ingest_mode == "pull":
        tags.append("rtsp")
        tags.append(f"rtsp-{record.rtsp_transport}")
        if record.rtsp_any_port:
            tags.append("rtsp-any-port")
    if record.source_kind == "mock-video":
        tags.append("mock-video")
    if record.system_managed:
        tags.append("system-managed")
    return {
        "id": record.id,
        "siteId": record.site_id,
        "name": record.name,
        "zone": record.zone,
        "streamUrl": record.rtsp_url,
        "liveStreamUrl": media_client.build_hls_url(record.path_name) if path_state and path_state.ready else None,
        "playbackPath": record.path_name,
        "rtspTransport": record.rtsp_transport,
        "rtspAnyPort": record.rtsp_any_port,
        "health": health,
        "fps": 0,
        "resolution": "Unknown",
        "uptimePct": 100.0 if health == "healthy" else (50.0 if health == "warning" else 0.0),
        "lastSeenAt": (
            (path_state.ready_time or path_state.online_time) if path_state else None
        )
        or record.created_at,
        "tags": tags,
    }


def _serialize_live_tile(
    record: CameraRecord,
    path_state: PathState | None,
    media_client: MediaMtxClient,
) -> dict[str, object]:
    is_live = bool(path_state and path_state.ready)
    return {
        "cameraId": record.id,
        "isLive": is_live,
        "latencyMs": 250 if is_live else 0,
        "bitrateKbps": 0,
        "detections": [],
        "hlsUrl": media_client.build_hls_url(record.path_name) if is_live else None,
    }


def _serialize_device(camera: dict[str, object]) -> dict[str, object]:
    hostname = extract_host_label(str(camera["streamUrl"]))
    health = str(camera["health"])
    return {
        "id": f"dev-{camera['id']}",
        "cameraId": camera["id"],
        "siteId": camera["siteId"],
        "name": camera["name"],
        "type": "camera",
        "model": "RTSP Camera",
        "ipAddress": hostname,
        "firmware": "unknown",
        "health": health,
        "lastHeartbeatAt": camera["lastSeenAt"],
        "uptimePct": camera["uptimePct"],
        "packetLossPct": 0.0 if health == "healthy" else 1.0,
        "tags": list(camera.get("tags", [])),
    }


def _serialize_vision_source(
    record: CameraRecord,
    path_state: PathState | None,
    media_client: MediaMtxClient,
) -> dict[str, object]:
    return {
        "id": record.id,
        "siteId": record.site_id,
        "cameraId": record.id,
        "cameraName": record.name,
        "pathName": record.path_name,
        "relayRtspUrl": f"rtsp://mediamtx:8554/{record.path_name}",
        "liveStreamUrl": media_client.build_hls_url(record.path_name) if path_state and path_state.ready else None,
        "health": path_state_to_health(path_state),
        "sourceKind": record.source_kind,
        "ingestMode": record.ingest_mode,
    }


def _serialize_overview(cameras: list[dict[str, object]], live_tiles: list[dict[str, object]]) -> dict[str, object]:
    total = len(cameras)
    live = sum(1 for tile in live_tiles if tile["isLive"])
    offline = sum(1 for camera in cameras if camera["health"] == "offline")
    warning = sum(1 for camera in cameras if camera["health"] == "warning")
    critical = sum(1 for camera in cameras if camera["health"] == "critical")
    healthy = sum(1 for camera in cameras if camera["health"] == "healthy")

    return {
        "metrics": [
            {
                "label": "Configured Cameras",
                "value": str(total),
                "delta": "RTSP sources",
                "trend": "flat",
            },
            {
                "label": "Live Streams",
                "value": f"{live}/{total}" if total else "0/0",
                "delta": "MediaMTX relay",
                "trend": "up" if live else "flat",
            },
            {
                "label": "Recorded Cameras",
                "value": str(total),
                "delta": "Playback enabled",
                "trend": "flat",
            },
            {
                "label": "Offline Cameras",
                "value": str(offline),
                "delta": "Needs source review" if offline else "All online",
                "trend": "up" if offline else "flat",
            },
        ],
        "topAlerts": [],
        "activeIncidents": [],
        "streamHealth": [
            {"label": "Healthy", "value": healthy},
            {"label": "Warning", "value": warning},
            {"label": "Critical", "value": critical},
            {"label": "Offline", "value": offline},
        ],
    }


def _serialize_playback_segment(
    record: CameraRecord,
    index: int,
    span: RecordingSpan,
) -> dict[str, object]:
    start_at = datetime.fromisoformat(span.start.replace("Z", "+00:00"))
    end_at = start_at.timestamp() + span.duration
    return {
        "id": f"seg-{record.id}-{index}",
        "cameraId": record.id,
        "startAt": start_at.astimezone(UTC).isoformat(),
        "endAt": datetime.fromtimestamp(end_at, tz=UTC).isoformat(),
        "alerts": 0,
        "motionScore": 1.0,
        "durationSec": span.duration,
        "playbackUrl": span.playback_url,
        "downloadUrl": span.download_url,
    }


def _get_camera_or_404(camera_store: CameraStore, camera_id: str) -> CameraRecord:
    record = camera_store.get_camera(camera_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Camera {camera_id} was not found.",
        )
    return record


def _slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def _build_mock_video_slug(stem: str) -> str:
    slug = _slugify(stem)
    if len(slug) <= 48:
        return slug
    digest = hashlib.sha1(stem.encode("utf-8")).hexdigest()[:8]
    return f"{slug[:39].rstrip('-')}-{digest}"


def _require_internal_token(
    x_qaongdur_internal_token: Annotated[str | None, Header()] = None,
    settings: Annotated[Settings, Depends(get_settings)] = None,
) -> None:
    if not x_qaongdur_internal_token or x_qaongdur_internal_token != settings.internal_service_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid internal service token.",
        )


def _titleize(stem: str) -> str:
    return stem.replace("-", " ").replace("_", " ").title()


def _discover_mock_video_files(root: Path) -> list[Path]:
    supported_files = [
        file_path
        for file_path in sorted(root.iterdir())
        if file_path.is_file() and file_path.suffix.lower() in SUPPORTED_MOCK_VIDEO_SUFFIXES
    ]
    if not supported_files:
        return []

    custom_files = [
        file_path for file_path in supported_files if file_path.name not in LEGACY_MOCK_VIDEO_FILES
    ]
    selected_files = custom_files or supported_files
    deduped_by_stem: dict[str, Path] = {}
    for file_path in selected_files:
        existing = deduped_by_stem.get(file_path.stem)
        if existing is None or file_path.stat().st_size > existing.stat().st_size:
            deduped_by_stem[file_path.stem] = file_path
    return sorted(deduped_by_stem.values(), key=lambda file_path: file_path.name.lower())


def _discover_mock_video_cameras(settings: Settings) -> list[CameraRecord]:
    if not settings.mock_video_dir:
        return []

    root = Path(settings.mock_video_dir)
    if not root.exists():
        return []

    cameras: list[CameraRecord] = []
    for file_path in _discover_mock_video_files(root):
        stem = _build_mock_video_slug(file_path.stem)
        if not stem:
            continue
        path_name = f"{settings.mock_video_path_prefix}-{stem}"
        cameras.append(
            CameraRecord(
                id=f"cam-{path_name}",
                site_id=settings.default_site_id,
                name=_titleize(file_path.stem),
                zone=settings.mock_video_zone,
                rtsp_url=f"{settings.mock_video_rtsp_base_url.rstrip('/')}/{path_name}",
                path_name=path_name,
                created_at=datetime.now(tz=UTC).isoformat(),
                ingest_mode="publish",
                system_managed=True,
                source_kind="mock-video",
                source_ref=str(file_path),
            )
        )
    return cameras


def _sync_mock_video_inventory(camera_store: CameraStore, settings: Settings) -> None:
    camera_store.sync_system_cameras(
        source_kind="mock-video",
        cameras=_discover_mock_video_cameras(settings),
    )


def _list_records(camera_store: CameraStore, settings: Settings) -> list[CameraRecord]:
    _sync_mock_video_inventory(camera_store, settings)
    return camera_store.list_cameras()


async def _list_path_states(
    records: list[CameraRecord],
    media_client: MediaMtxClient,
) -> dict[str, PathState]:
    if not records:
        return {}

    try:
        path_states = await media_client.list_paths()
    except MediaMtxError as error:
        raise raise_as_bad_gateway(error) from error

    missing_records = [
        record
        for record in records
        if record.ingest_mode == "pull" and record.path_name not in path_states
    ]
    if not missing_records:
        return path_states

    try:
        await asyncio.gather(
            *[
                media_client.add_camera_path(
                    path_name=record.path_name,
                    source=record.rtsp_url,
                    rtsp_transport=record.rtsp_transport,
                    rtsp_any_port=record.rtsp_any_port,
                )
                for record in missing_records
            ]
        )
        return await media_client.list_paths()
    except MediaMtxError as error:
        raise raise_as_bad_gateway(error) from error


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="Qaongdur Control API",
        version="0.1.0",
        summary="Keycloak-protected control plane surface for Qaongdur",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.control_api_cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/readyz")
    async def readyz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/v1/sites")
    async def list_sites(
        _: Annotated[KeycloakPrincipal, Depends(get_current_principal)],
        service_settings: Annotated[Settings, Depends(get_settings)],
    ) -> list[dict[str, str]]:
        return [_serialize_site(service_settings)]

    @app.get("/api/v1/cameras")
    async def list_cameras(
        _: Annotated[KeycloakPrincipal, Depends(get_current_principal)],
        camera_store: Annotated[CameraStore, Depends(get_camera_store)],
        media_client: Annotated[MediaMtxClient, Depends(get_mediamtx_client)],
        service_settings: Annotated[Settings, Depends(get_settings)],
        siteId: str | None = None,
    ) -> list[dict[str, object]]:
        records = _list_records(camera_store, service_settings)
        path_states = await _list_path_states(records, media_client)
        if siteId:
            records = [record for record in records if record.site_id == siteId]

        return [
            _serialize_camera(record, path_states.get(record.path_name), media_client)
            for record in records
        ]

    @app.post("/api/v1/cameras")
    async def create_camera(
        body: CameraCreateBody,
        _: Annotated[
            KeycloakPrincipal,
            Depends(require_roles("site-admin", "platform-admin")),
        ],
        camera_store: Annotated[CameraStore, Depends(get_camera_store)],
        media_client: Annotated[MediaMtxClient, Depends(get_mediamtx_client)],
        service_settings: Annotated[Settings, Depends(get_settings)],
    ) -> dict[str, object]:
        record = camera_store.prepare_camera(
            site_id=body.siteId or service_settings.default_site_id,
            name=body.name,
            zone=body.zone,
            rtsp_url=body.rtspUrl,
            rtsp_transport=body.rtspTransport,
            rtsp_any_port=body.rtspAnyPort,
        )

        try:
            await media_client.add_camera_path(
                path_name=record.path_name,
                source=record.rtsp_url,
                rtsp_transport=record.rtsp_transport,
                rtsp_any_port=record.rtsp_any_port,
            )
        except MediaMtxError as error:
            raise raise_as_bad_gateway(error) from error

        camera_store.save_camera(record)
        return _serialize_camera(record, None, media_client)

    @app.post("/api/v1/cameras/{camera_id}/reconnect")
    async def reconnect_camera(
        camera_id: str,
        _: Annotated[
            KeycloakPrincipal,
            Depends(require_roles("site-admin", "platform-admin")),
        ],
        camera_store: Annotated[CameraStore, Depends(get_camera_store)],
        media_client: Annotated[MediaMtxClient, Depends(get_mediamtx_client)],
        service_settings: Annotated[Settings, Depends(get_settings)],
    ) -> dict[str, object]:
        _sync_mock_video_inventory(camera_store, service_settings)
        record = _get_camera_or_404(camera_store, camera_id)

        if record.ingest_mode != "pull":
            try:
                path_states = await media_client.list_paths()
            except MediaMtxError as error:
                raise raise_as_bad_gateway(error) from error
            return _serialize_camera(record, path_states.get(record.path_name), media_client)

        try:
            await media_client.reconnect_camera_path(
                path_name=record.path_name,
                source=record.rtsp_url,
                rtsp_transport=record.rtsp_transport,
                rtsp_any_port=record.rtsp_any_port,
            )
            path_states = await media_client.list_paths()
        except MediaMtxError as error:
            raise raise_as_bad_gateway(error) from error

        return _serialize_camera(record, path_states.get(record.path_name), media_client)

    @app.delete("/api/v1/cameras/{camera_id}")
    async def delete_camera(
        camera_id: str,
        _: Annotated[
            KeycloakPrincipal,
            Depends(require_roles("site-admin", "platform-admin")),
        ],
        camera_store: Annotated[CameraStore, Depends(get_camera_store)],
        media_client: Annotated[MediaMtxClient, Depends(get_mediamtx_client)],
        service_settings: Annotated[Settings, Depends(get_settings)],
    ) -> dict[str, object]:
        _sync_mock_video_inventory(camera_store, service_settings)
        record = _get_camera_or_404(camera_store, camera_id)

        if record.system_managed:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "System-managed mock cameras are derived from the local Video directory "
                    "and cannot be removed while the mock-video stack is enabled."
                ),
            )

        try:
            await media_client.delete_camera_path(
                path_name=record.path_name,
                ignore_missing=True,
            )
        except MediaMtxError as error:
            raise raise_as_bad_gateway(error) from error

        deleted_record = camera_store.delete_camera(camera_id)
        if deleted_record is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Camera {camera_id} was removed before the delete completed.",
            )

        return {
            "deleted": True,
            "cameraId": deleted_record.id,
            "name": deleted_record.name,
        }

    @app.get("/api/v1/live-tiles")
    async def list_live_tiles(
        _: Annotated[KeycloakPrincipal, Depends(get_current_principal)],
        camera_store: Annotated[CameraStore, Depends(get_camera_store)],
        media_client: Annotated[MediaMtxClient, Depends(get_mediamtx_client)],
        service_settings: Annotated[Settings, Depends(get_settings)],
        siteId: str | None = None,
    ) -> list[dict[str, object]]:
        records = _list_records(camera_store, service_settings)
        path_states = await _list_path_states(records, media_client)
        if siteId:
            records = [record for record in records if record.site_id == siteId]

        return [
            _serialize_live_tile(record, path_states.get(record.path_name), media_client)
            for record in records
        ]

    @app.get("/api/v1/overview")
    async def get_overview(
        _: Annotated[KeycloakPrincipal, Depends(get_current_principal)],
        camera_store: Annotated[CameraStore, Depends(get_camera_store)],
        media_client: Annotated[MediaMtxClient, Depends(get_mediamtx_client)],
        service_settings: Annotated[Settings, Depends(get_settings)],
        siteId: str | None = None,
    ) -> dict[str, object]:
        records = _list_records(camera_store, service_settings)
        path_states = await _list_path_states(records, media_client)
        if siteId:
            records = [record for record in records if record.site_id == siteId]

        cameras = [
            _serialize_camera(record, path_states.get(record.path_name), media_client)
            for record in records
        ]
        live_tiles = [
            _serialize_live_tile(record, path_states.get(record.path_name), media_client)
            for record in records
        ]
        return _serialize_overview(cameras, live_tiles)

    @app.get("/api/v1/alerts")
    async def list_alerts(
        _: Annotated[KeycloakPrincipal, Depends(get_current_principal)],
        siteId: str | None = None,
        cameraId: str | None = None,
        severity: str | None = None,
        status_filter: str | None = Query(default=None, alias="status"),
        search: str | None = None,
    ) -> list[dict[str, object]]:
        del siteId, cameraId, severity, status_filter, search
        return []

    @app.get("/api/v1/incidents")
    async def list_incidents(
        _: Annotated[KeycloakPrincipal, Depends(get_current_principal)],
    ) -> list[dict[str, object]]:
        return []

    @app.get("/api/v1/incidents/{incident_id}")
    async def get_incident(
        incident_id: str,
        _: Annotated[KeycloakPrincipal, Depends(get_current_principal)],
    ) -> dict[str, object]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident {incident_id} was not found.",
        )

    @app.post("/api/v1/playback/search")
    async def search_playback(
        body: PlaybackSearchBody,
        _: Annotated[KeycloakPrincipal, Depends(get_current_principal)],
        camera_store: Annotated[CameraStore, Depends(get_camera_store)],
        media_client: Annotated[MediaMtxClient, Depends(get_mediamtx_client)],
        service_settings: Annotated[Settings, Depends(get_settings)],
    ) -> list[dict[str, object]]:
        records = _list_records(camera_store, service_settings)
        if body.cameraIds:
            allowed_ids = set(body.cameraIds)
            records = [record for record in records if record.id in allowed_ids]

        path_states = await _list_path_states(records, media_client)

        try:
            recording_sets = await asyncio.gather(
                *[
                    media_client.list_recordings(
                        path_name=record.path_name,
                        start=body.from_,
                        end=body.to,
                    )
                    for record in records
                ]
            )
        except MediaMtxError as error:
            raise raise_as_bad_gateway(error) from error

        segments: list[dict[str, object]] = []
        for record, spans in zip(records, recording_sets, strict=False):
            path_state = path_states.get(record.path_name)
            filtered_spans = filter_playback_spans(
                spans,
                is_path_live=bool(path_state and path_state.ready),
                segment_duration_seconds=service_settings.mediamtx_record_segment_duration_seconds,
            )
            for index, span in enumerate(filtered_spans, start=1):
                segments.append(_serialize_playback_segment(record, index, span))

        segments.sort(key=lambda item: str(item["startAt"]))
        return segments

    @app.get("/api/v1/internal/vision/sources")
    async def list_internal_vision_sources(
        _: Annotated[None, Depends(_require_internal_token)],
        camera_store: Annotated[CameraStore, Depends(get_camera_store)],
        media_client: Annotated[MediaMtxClient, Depends(get_mediamtx_client)],
        service_settings: Annotated[Settings, Depends(get_settings)],
    ) -> dict[str, object]:
        records = _list_records(camera_store, service_settings)
        path_states = await _list_path_states(records, media_client)
        sources = [
            _serialize_vision_source(record, path_states.get(record.path_name), media_client)
            for record in records
        ]
        return {
            "count": len(sources),
            "sources": sources,
        }

    @app.get("/api/v1/vision/status")
    async def get_vision_status(
        _: Annotated[KeycloakPrincipal, Depends(get_current_principal)],
        vision_client: Annotated[VisionServiceClient, Depends(get_vision_service_client)],
    ) -> dict[str, object]:
        try:
            return await vision_client.get_status()
        except VisionServiceError as error:
            raise raise_vision_bad_gateway(error) from error

    @app.get("/api/v1/vision/sources")
    async def list_vision_sources(
        _: Annotated[KeycloakPrincipal, Depends(get_current_principal)],
        vision_client: Annotated[VisionServiceClient, Depends(get_vision_service_client)],
    ) -> dict[str, object]:
        try:
            return await vision_client.list_sources()
        except VisionServiceError as error:
            raise raise_vision_bad_gateway(error) from error

    @app.get("/api/v1/vision/mock-sources")
    async def list_vision_sources_legacy(
        principal: Annotated[KeycloakPrincipal, Depends(get_current_principal)],
        vision_client: Annotated[VisionServiceClient, Depends(get_vision_service_client)],
    ) -> dict[str, object]:
        del principal
        try:
            return await vision_client.list_sources()
        except VisionServiceError as error:
            raise raise_vision_bad_gateway(error) from error

    @app.post("/api/v1/vision/scan")
    async def trigger_vision_scan(
        body: VisionMockJobBody,
        _: Annotated[
            KeycloakPrincipal,
            Depends(require_roles("site-admin", "platform-admin")),
        ],
        vision_client: Annotated[VisionServiceClient, Depends(get_vision_service_client)],
    ) -> dict[str, object]:
        try:
            return await vision_client.trigger_scan(source_ids=body.sourceIds)
        except VisionServiceError as error:
            raise raise_vision_bad_gateway(error) from error

    @app.post("/api/v1/vision/mock-jobs/run")
    async def trigger_vision_scan_legacy(
        body: VisionMockJobBody,
        principal: Annotated[
            KeycloakPrincipal,
            Depends(require_roles("site-admin", "platform-admin")),
        ],
        vision_client: Annotated[VisionServiceClient, Depends(get_vision_service_client)],
    ) -> dict[str, object]:
        del principal
        try:
            return await vision_client.trigger_scan(source_ids=body.sourceIds)
        except VisionServiceError as error:
            raise raise_vision_bad_gateway(error) from error

    @app.get("/api/v1/vision/crop-tracks")
    async def list_vision_crop_tracks(
        _: Annotated[KeycloakPrincipal, Depends(get_current_principal)],
        vision_client: Annotated[VisionServiceClient, Depends(get_vision_service_client)],
        sourceId: str | None = None,
        cameraId: str | None = None,
        label: str | None = None,
        fromAt: str | None = None,
        toAt: str | None = None,
    ) -> dict[str, object]:
        try:
            return await vision_client.list_crop_tracks(
                source_id=sourceId,
                camera_id=cameraId,
                label=label,
                from_at=fromAt,
                to_at=toAt,
            )
        except VisionServiceError as error:
            raise raise_vision_bad_gateway(error) from error

    @app.get("/api/v1/vision/crop-tracks/{track_id}")
    async def get_vision_crop_track(
        track_id: str,
        _: Annotated[KeycloakPrincipal, Depends(get_current_principal)],
        vision_client: Annotated[VisionServiceClient, Depends(get_vision_service_client)],
    ) -> dict[str, object]:
        try:
            return await vision_client.get_crop_track(track_id)
        except VisionServiceError as error:
            raise raise_vision_bad_gateway(error) from error

    @app.get("/api/v1/devices")
    async def list_devices(
        _: Annotated[KeycloakPrincipal, Depends(get_current_principal)],
        camera_store: Annotated[CameraStore, Depends(get_camera_store)],
        media_client: Annotated[MediaMtxClient, Depends(get_mediamtx_client)],
        service_settings: Annotated[Settings, Depends(get_settings)],
        siteId: str | None = None,
    ) -> list[dict[str, object]]:
        records = _list_records(camera_store, service_settings)
        path_states = await _list_path_states(records, media_client)
        if siteId:
            records = [record for record in records if record.site_id == siteId]

        cameras = [
            _serialize_camera(record, path_states.get(record.path_name), media_client)
            for record in records
        ]
        return [_serialize_device(camera) for camera in cameras]

    @app.get("/api/v1/auth/me")
    async def get_auth_me(
        principal: Annotated[KeycloakPrincipal, Depends(get_current_principal)],
        service_settings: Annotated[Settings, Depends(get_settings)],
    ) -> dict[str, object]:
        return {
            "service": service_settings.service_name,
            "issuer": service_settings.keycloak_issuer_url,
            "audience": service_settings.keycloak_audience,
            "checkedAt": datetime.now(tz=UTC).isoformat(),
            "user": _serialize_principal(principal),
        }

    @app.get("/api/v1/settings")
    async def get_system_settings(
        principal: Annotated[KeycloakPrincipal, Depends(get_current_principal)],
        service_settings: Annotated[Settings, Depends(get_settings)],
    ) -> dict[str, object]:
        return {
            "checkedAt": datetime.now(tz=UTC).isoformat(),
            "auth": {
                "issuer": service_settings.keycloak_issuer_url,
                "audience": service_settings.keycloak_audience,
                "stepUpAcr": service_settings.keycloak_step_up_acr,
                "user": _serialize_principal(principal),
            },
            "recording": {
                "segmentDurationSeconds": service_settings.mediamtx_record_segment_duration_seconds,
                "playbackPublicUrl": service_settings.mediamtx_playback_public_url,
                "hlsPublicUrl": service_settings.mediamtx_hls_public_url,
            },
            "vision": {
                "serviceUrl": service_settings.vision_service_url,
                "autoIngest": True,
                "notes": [
                    "Recorded chunks are processed automatically after they land in MediaMTX storage.",
                    "Auth controls now live on the Settings page.",
                    "Runtime settings are env-backed right now; this page is the planning surface for future writable config.",
                ],
            },
        }

    @app.get("/api/v1/auth/allowed-actions")
    async def get_allowed_actions(
        principal: Annotated[KeycloakPrincipal, Depends(get_current_principal)],
    ) -> dict[str, list[str]]:
        actions: list[str] = ["view-live", "view-alerts"]
        role_actions: dict[PlatformRole, list[str]] = {
            "viewer": [],
            "operator": ["acknowledge-alert", "launch-agent-investigation"],
            "reviewer": ["approve-evidence-export"],
            "site-admin": ["approve-site-maintenance", "override-camera-health"],
            "platform-admin": ["purge-evidence", "restart-edge-bridge"],
        }

        for role in sorted(principal.roles):
            actions.extend(role_actions.get(role, []))

        return {"actions": sorted(set(actions))}

    @app.post("/api/v1/agent/actions/evidence-export")
    async def export_evidence(
        body: AgentApprovalBody,
        principal: Annotated[
            KeycloakPrincipal,
            Depends(require_roles("operator", "reviewer", "site-admin", "platform-admin")),
        ],
    ) -> dict[str, object]:
        if not body.approvalPath:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="approvalPath must record the UI confirmation path.",
            )

        audit_entry = audit_logger.record(
            principal=principal,
            action=body.action,
            approval_path=body.approvalPath,
            outcome="approved",
            note=body.rationale,
        )

        return {
            "action": body.action,
            "approvalPath": body.approvalPath,
            "rationale": body.rationale,
            "requiresStepUp": body.requiresStepUp,
            "approved": True,
            "approvedAt": audit_entry.timestamp,
            "approvedBy": principal.username,
            "stepUpSatisfied": not body.requiresStepUp
            or has_required_acr(principal, get_settings().keycloak_step_up_acr),
        }

    @app.post("/api/v1/agent/actions/purge-evidence")
    async def purge_evidence(
        body: AgentApprovalBody,
        principal: Annotated[
            KeycloakPrincipal,
            Depends(require_roles("platform-admin")),
        ],
        service_settings: Annotated[Settings, Depends(get_settings)],
    ) -> dict[str, object]:
        if not body.approvalPath:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="approvalPath must record the UI confirmation path.",
            )

        if not has_required_acr(principal, service_settings.keycloak_step_up_acr):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "Step-up authentication required for destructive actions. "
                    f"Expected ACR {service_settings.keycloak_step_up_acr}."
                ),
            )

        audit_entry = audit_logger.record(
            principal=principal,
            action=body.action,
            approval_path=body.approvalPath,
            outcome="approved-with-step-up",
            note=body.rationale,
        )

        return {
            "action": body.action,
            "approvalPath": body.approvalPath,
            "rationale": body.rationale,
            "requiresStepUp": True,
            "approved": True,
            "approvedAt": audit_entry.timestamp,
            "approvedBy": principal.username,
            "stepUpSatisfied": True,
        }

    return app


app = create_app()


def run() -> None:
    settings = get_settings()
    uvicorn.run(
        "control_api.main:app",
        host=settings.control_api_host,
        port=settings.control_api_port,
        reload=settings.env == "development",
    )


if __name__ == "__main__":
    run()
