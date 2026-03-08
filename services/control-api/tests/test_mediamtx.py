from control_api.mediamtx import (
    MediaMtxClient,
    RecordingSpan,
    build_camera_path_payload,
    filter_playback_spans,
    path_state_to_health,
)


def test_build_public_urls() -> None:
    client = MediaMtxClient(
        api_url="http://mediamtx:9997",
        api_user="qaongdur-api",
        api_password="qaongdur-api",
        hls_public_url="http://localhost:8888",
        playback_internal_url="http://mediamtx:9996",
        playback_public_url="http://localhost:9996",
    )

    assert client.build_hls_url("cam-123") == "http://localhost:8888/cam-123/index.m3u8"
    assert "format=mp4" in client.build_playback_url(
        path_name="cam-123",
        start="2026-03-07T10:00:00Z",
        duration=30.0,
    )


def test_path_state_to_health_maps_ready_state() -> None:
    assert path_state_to_health(None) == "offline"


def test_filter_playback_spans_drops_open_segment_for_live_paths() -> None:
    spans = [
        RecordingSpan(
            start="2026-03-07T10:00:00Z",
            duration=30.0,
            playback_url="http://localhost:9996/get?segment=1",
        ),
        RecordingSpan(
            start="2026-03-07T10:00:30Z",
            duration=8.0,
            playback_url="http://localhost:9996/get?segment=2",
        ),
    ]

    filtered = filter_playback_spans(
        spans,
        is_path_live=True,
        segment_duration_seconds=30,
    )

    assert filtered == [spans[0]]


def test_filter_playback_spans_keeps_partial_segments_for_stopped_paths() -> None:
    spans = [
        RecordingSpan(
            start="2026-03-07T10:00:00Z",
            duration=12.0,
            playback_url="http://localhost:9996/get?segment=1",
        )
    ]

    filtered = filter_playback_spans(
        spans,
        is_path_live=False,
        segment_duration_seconds=30,
    )

    assert filtered == spans


def test_build_camera_path_payload_defaults_to_automatic_transport() -> None:
    payload = build_camera_path_payload(source="rtsp://camera.local/stream")

    assert payload == {
        "source": "rtsp://camera.local/stream",
        "rtspTransport": "automatic",
    }


def test_build_camera_path_payload_includes_any_port_when_enabled() -> None:
    payload = build_camera_path_payload(
        source="rtsp://camera.local/stream",
        rtsp_transport="udp",
        rtsp_any_port=True,
    )

    assert payload == {
        "source": "rtsp://camera.local/stream",
        "rtspTransport": "udp",
        "rtspAnyPort": True,
    }
