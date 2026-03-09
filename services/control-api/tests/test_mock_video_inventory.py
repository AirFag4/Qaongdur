from __future__ import annotations

from control_api.config import Settings
from control_api.main import _discover_mock_video_cameras


def test_discover_mock_video_cameras_respects_max_sources(tmp_path) -> None:
    small = tmp_path / "small-scene.mp4"
    large = tmp_path / "large-scene.mp4"
    small.write_bytes(b"0" * 128)
    large.write_bytes(b"1" * 512)

    settings = Settings(
        _env_file=None,
        mock_video_dir=str(tmp_path),
        mock_video_max_sources=1,
    )

    cameras = _discover_mock_video_cameras(settings)

    assert len(cameras) == 1
    assert cameras[0].source_ref == str(large)
    assert cameras[0].id.startswith("cam-mock-video-")

