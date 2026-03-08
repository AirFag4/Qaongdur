from __future__ import annotations

from pathlib import Path
import re

import cv2

from .domain import MockVideoSource


def _slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def _titleize(stem: str) -> str:
    return stem.replace("-", " ").replace("_", " ").title()


def discover_mock_sources(video_dir: str, *, default_site_id: str) -> list[MockVideoSource]:
    root = Path(video_dir)
    if not root.exists():
        return []

    sources: list[MockVideoSource] = []
    for file_path in sorted(root.glob("*.mp4")):
        stem = _slugify(file_path.stem)
        camera_name = _titleize(file_path.stem)
        capture = cv2.VideoCapture(str(file_path))
        frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        source_fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        capture.release()
        duration_sec = (frame_count / source_fps) if frame_count and source_fps else 0.0

        sources.append(
            MockVideoSource(
                id=f"source-{stem}",
                site_id=default_site_id,
                camera_id=f"cam-{stem}",
                camera_name=camera_name,
                file_path=str(file_path),
                duration_sec=duration_sec,
                frame_width=width,
                frame_height=height,
                source_fps=source_fps,
            )
        )

    return sources
