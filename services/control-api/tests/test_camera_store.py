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


def test_camera_store_deletes_camera_records(tmp_path) -> None:
    store = CameraStore(str(tmp_path / "cameras.json"))

    record = store.prepare_camera(
        site_id="site-local-01",
        name="Dock Camera",
        zone="Dock",
        rtsp_url="rtsp://camera.local/dock",
    )
    store.save_camera(record)

    deleted = store.delete_camera(record.id)

    assert deleted is not None
    assert deleted.id == record.id
    assert store.get_camera(record.id) is None
    assert store.list_cameras() == []
