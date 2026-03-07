from vision_service.demo_data import DEMO_PIPELINES


def test_demo_pipelines_are_seeded() -> None:
    assert DEMO_PIPELINES
    assert DEMO_PIPELINES[0]["recommendedAlert"]["title"]
