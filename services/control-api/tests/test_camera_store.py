from control_api.camera_store import CameraStore


def test_camera_store_persists_camera_records(tmp_path) -> None:
    store = CameraStore(str(tmp_path / "cameras.json"))

    record = store.prepare_camera(
        site_id="site-local-01",
        name="Gate Camera",
        zone="North Gate",
        rtsp_url="rtsp://camera.local/stream",
    )
    store.save_camera(record)

    cameras = store.list_cameras()

    assert len(cameras) == 1
    assert cameras[0].id == record.id
    assert cameras[0].path_name == record.path_name
    assert cameras[0].rtsp_url == "rtsp://camera.local/stream"
