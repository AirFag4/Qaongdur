from datetime import UTC, datetime

from control_api.camera_store import CameraRecord, CameraStore


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


def test_camera_store_syncs_system_managed_cameras_without_deleting_manual_records(tmp_path) -> None:
    store = CameraStore(str(tmp_path / "cameras.json"))

    manual_record = store.prepare_camera(
        site_id="site-local-01",
        name="Manual Camera",
        zone="Dock",
        rtsp_url="rtsp://camera.local/manual",
    )
    store.save_camera(manual_record)

    store.sync_system_cameras(
        source_kind="mock-video",
        cameras=[
            CameraRecord(
                id="cam-mock-video-people-walking",
                site_id="site-local-01",
                name="People Walking",
                zone="Mock Video Lab",
                rtsp_url="rtsp://mediamtx:8554/mock-video-people-walking",
                path_name="mock-video-people-walking",
                created_at=datetime.now(tz=UTC).isoformat(),
                ingest_mode="publish",
                system_managed=True,
                source_kind="mock-video",
                source_ref="/mock-videos/people-walking.mp4",
            )
        ],
    )

    records = {record.id: record for record in store.list_cameras()}

    assert manual_record.id in records
    assert "cam-mock-video-people-walking" in records
    assert records["cam-mock-video-people-walking"].system_managed is True
    assert records["cam-mock-video-people-walking"].ingest_mode == "publish"
