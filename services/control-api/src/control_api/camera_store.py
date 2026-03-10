from __future__ import annotations

import json
import threading
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from uuid import uuid4

from .config import get_settings


@dataclass(slots=True)
class CameraRecord:
    id: str
    site_id: str
    name: str
    zone: str
    rtsp_url: str
    path_name: str
    created_at: str
    latitude: float | None = None
    longitude: float | None = None
    heading: float | None = None
    location_note: str | None = None
    ingest_mode: str = "pull"
    system_managed: bool = False
    source_kind: str = "rtsp"
    source_ref: str | None = None
    rtsp_transport: str = "automatic"
    rtsp_any_port: bool = False


class CameraStore:
    def __init__(self, path: str) -> None:
        self._path = Path(path)
        self._lock = threading.Lock()

    def list_cameras(self) -> list[CameraRecord]:
        payload = self._read_payload()
        return [CameraRecord(**item) for item in payload.get("cameras", [])]

    def get_camera(self, camera_id: str) -> CameraRecord | None:
        return next(
            (camera for camera in self.list_cameras() if camera.id == camera_id),
            None,
        )

    def prepare_camera(
        self,
        *,
        site_id: str,
        name: str,
        zone: str,
        rtsp_url: str,
        latitude: float | None = None,
        longitude: float | None = None,
        heading: float | None = None,
        location_note: str | None = None,
        rtsp_transport: str = "automatic",
        rtsp_any_port: bool = False,
    ) -> CameraRecord:
        camera_id = f"cam-{uuid4().hex[:10]}"
        return CameraRecord(
            id=camera_id,
            site_id=site_id,
            name=name.strip(),
            zone=zone.strip(),
            latitude=latitude,
            longitude=longitude,
            heading=heading,
            location_note=location_note.strip() if location_note else None,
            rtsp_url=rtsp_url.strip(),
            path_name=camera_id,
            created_at=datetime.now(tz=UTC).isoformat(),
            ingest_mode="pull",
            system_managed=False,
            source_kind="rtsp",
            source_ref=None,
            rtsp_transport=rtsp_transport,
            rtsp_any_port=rtsp_any_port,
        )

    def save_camera(self, camera: CameraRecord) -> None:
        with self._lock:
            payload = self._read_payload()
            cameras = payload.setdefault("cameras", [])
            cameras.append(asdict(camera))
            self._write_payload(payload)

    def delete_camera(self, camera_id: str) -> CameraRecord | None:
        with self._lock:
            payload = self._read_payload()
            cameras = payload.setdefault("cameras", [])
            retained: list[dict[str, object]] = []
            deleted: CameraRecord | None = None

            for item in cameras:
                record = CameraRecord(**item)
                if record.id == camera_id and deleted is None:
                    deleted = record
                    continue
                retained.append(item)

            if deleted is None:
                return None

            payload["cameras"] = retained
            self._write_payload(payload)
            return deleted

    def sync_system_cameras(
        self,
        *,
        source_kind: str,
        cameras: list[CameraRecord],
    ) -> None:
        with self._lock:
            payload = self._read_payload()
            existing_items = payload.setdefault("cameras", [])
            existing_by_id = {item.get("id"): item for item in existing_items}
            retained = [
                item
                for item in existing_items
                if not (
                    item.get("system_managed") is True
                    and item.get("source_kind") == source_kind
                )
            ]

            for camera in cameras:
                existing = existing_by_id.get(camera.id)
                retained.append(
                    asdict(
                        CameraRecord(
                            id=camera.id,
                            site_id=camera.site_id,
                            name=camera.name,
                            zone=camera.zone,
                            latitude=(
                                float(existing["latitude"])
                                if existing and existing.get("latitude") is not None
                                else camera.latitude
                            ),
                            longitude=(
                                float(existing["longitude"])
                                if existing and existing.get("longitude") is not None
                                else camera.longitude
                            ),
                            heading=(
                                float(existing["heading"])
                                if existing and existing.get("heading") is not None
                                else camera.heading
                            ),
                            location_note=(
                                str(existing["location_note"])
                                if existing and existing.get("location_note") is not None
                                else camera.location_note
                            ),
                            rtsp_url=camera.rtsp_url,
                            path_name=camera.path_name,
                            created_at=(
                                str(existing.get("created_at"))
                                if existing and existing.get("created_at")
                                else camera.created_at
                            ),
                            ingest_mode=camera.ingest_mode,
                            system_managed=camera.system_managed,
                            source_kind=camera.source_kind,
                            source_ref=camera.source_ref,
                            rtsp_transport=(
                                str(existing.get("rtsp_transport"))
                                if existing and existing.get("rtsp_transport")
                                else camera.rtsp_transport
                            ),
                            rtsp_any_port=bool(
                                existing.get("rtsp_any_port", camera.rtsp_any_port)
                            )
                            if existing
                            else camera.rtsp_any_port,
                        )
                    )
                )

            payload["cameras"] = retained
            self._write_payload(payload)

    def _read_payload(self) -> dict[str, object]:
        if not self._path.exists():
            return {"cameras": []}

        try:
            return json.loads(self._path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {"cameras": []}

    def _write_payload(self, payload: dict[str, object]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self._path.with_suffix(".tmp")
        temp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        temp_path.replace(self._path)


@lru_cache(maxsize=1)
def get_camera_store() -> CameraStore:
    return CameraStore(get_settings().camera_store_path)
