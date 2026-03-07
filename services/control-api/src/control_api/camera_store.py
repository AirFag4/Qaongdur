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
    ) -> CameraRecord:
        camera_id = f"cam-{uuid4().hex[:10]}"
        return CameraRecord(
            id=camera_id,
            site_id=site_id,
            name=name.strip(),
            zone=zone.strip(),
            rtsp_url=rtsp_url.strip(),
            path_name=camera_id,
            created_at=datetime.now(tz=UTC).isoformat(),
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
