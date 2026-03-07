from __future__ import annotations

from datetime import UTC, datetime, timedelta


def _timestamp(minutes_ago: int) -> str:
    return (datetime.now(tz=UTC) - timedelta(minutes=minutes_ago)).isoformat()


DEMO_PIPELINES = [
    {
        "sourceId": "demo-loading-dock",
        "siteId": "site-hcm-01",
        "cameraId": "cam-hcm-01-01",
        "summary": "Vehicle and person overlap near the loading dock safety lane.",
        "detections": [
            {
                "label": "Vehicle",
                "confidence": 0.94,
                "severity": "high",
                "boundingBox": {"x": 18, "y": 31, "width": 42, "height": 29},
            },
            {
                "label": "Person",
                "confidence": 0.88,
                "severity": "medium",
                "boundingBox": {"x": 63, "y": 28, "width": 12, "height": 35},
            },
        ],
        "recommendedAlert": {
            "title": "Vehicle wrong-way movement",
            "rule": "rule-5",
            "severity": "high",
        },
        "capturedAt": _timestamp(3),
    },
    {
        "sourceId": "demo-perimeter-south",
        "siteId": "site-bkk-01",
        "cameraId": "cam-bkk-01-07",
        "summary": "Two detections crossed the southern perimeter after-hours.",
        "detections": [
            {
                "label": "Person",
                "confidence": 0.91,
                "severity": "critical",
                "boundingBox": {"x": 14, "y": 21, "width": 13, "height": 36},
            },
            {
                "label": "Person",
                "confidence": 0.84,
                "severity": "high",
                "boundingBox": {"x": 47, "y": 24, "width": 14, "height": 37},
            },
        ],
        "recommendedAlert": {
            "title": "Perimeter breach",
            "rule": "rule-4",
            "severity": "critical",
        },
        "capturedAt": _timestamp(9),
    },
]
