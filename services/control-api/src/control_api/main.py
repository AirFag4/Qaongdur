from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Annotated

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Query, status
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


ALL_PLATFORM_ROLES: tuple[PlatformRole, ...] = (
    "platform-admin",
    "site-admin",
    "operator",
    "reviewer",
    "viewer",
)


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
    return {
        "id": record.id,
        "siteId": record.site_id,
        "name": record.name,
        "zone": record.zone,
        "streamUrl": record.rtsp_url,
        "liveStreamUrl": media_client.build_hls_url(record.path_name) if path_state and path_state.ready else None,
        "playbackPath": record.path_name,
        "health": health,
        "fps": 0,
        "resolution": "Unknown",
        "uptimePct": 100.0 if health == "healthy" else (50.0 if health == "warning" else 0.0),
        "lastSeenAt": (
            (path_state.ready_time or path_state.online_time) if path_state else None
        )
        or record.created_at,
        "tags": ["rtsp", "mediamtx", "recording-enabled"],
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
    }


def _get_camera_or_404(camera_store: CameraStore, camera_id: str) -> CameraRecord:
    record = camera_store.get_camera(camera_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Camera {camera_id} was not found.",
        )
    return record


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
        record for record in records if record.path_name not in path_states
    ]
    if not missing_records:
        return path_states

    try:
        await asyncio.gather(
            *[
                media_client.add_camera_path(
                    path_name=record.path_name,
                    source=record.rtsp_url,
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
        siteId: str | None = None,
    ) -> list[dict[str, object]]:
        records = camera_store.list_cameras()
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
        )

        try:
            await media_client.add_camera_path(
                path_name=record.path_name,
                source=record.rtsp_url,
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
    ) -> dict[str, object]:
        record = _get_camera_or_404(camera_store, camera_id)

        try:
            await media_client.reconnect_camera_path(
                path_name=record.path_name,
                source=record.rtsp_url,
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
    ) -> dict[str, object]:
        record = _get_camera_or_404(camera_store, camera_id)

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
        siteId: str | None = None,
    ) -> list[dict[str, object]]:
        records = camera_store.list_cameras()
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
        siteId: str | None = None,
    ) -> dict[str, object]:
        records = camera_store.list_cameras()
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
        records = camera_store.list_cameras()
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

    @app.get("/api/v1/devices")
    async def list_devices(
        _: Annotated[KeycloakPrincipal, Depends(get_current_principal)],
        camera_store: Annotated[CameraStore, Depends(get_camera_store)],
        media_client: Annotated[MediaMtxClient, Depends(get_mediamtx_client)],
        siteId: str | None = None,
    ) -> list[dict[str, object]]:
        records = camera_store.list_cameras()
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
