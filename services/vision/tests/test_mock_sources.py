from vision_service.mock_sources import build_mock_path_name, build_mock_stream_url, discover_mock_sources, slugify


def test_slugify_and_stream_helpers_match_mock_video_pathing() -> None:
    stem = slugify("People Walking")

    assert stem == "people-walking"
    assert build_mock_path_name(stem=stem, path_prefix="mock-video") == "mock-video-people-walking"
    assert (
        build_mock_stream_url(
            rtsp_base_url="rtsp://mediamtx:8554",
            path_name="mock-video-people-walking",
        )
        == "rtsp://mediamtx:8554/mock-video-people-walking"
    )


def test_discover_mock_sources_returns_empty_list_for_missing_directory() -> None:
    sources = discover_mock_sources(
        "/tmp/qaongdur-missing-video-dir",
        default_site_id="site-local-01",
        rtsp_base_url="rtsp://mediamtx:8554",
        path_prefix="mock-video",
        use_vms=True,
    )

    assert sources == []
