# Codex Prompt: Backend VMS and Vision AI Platform

You are Codex building the first backend for an open-source Docker-based VMS with AI enrichment. Build a practical backend architecture that supports camera inventory, live events, AI detections, incidents, playback metadata, and future agent actions.

## Primary Goal

Create a backend that is demoable early, but structurally ready for:

- object detection
- image and clip embeddings with MobileCLIP
- optional 1B to 2B class VLM enrichment when hardware allows
- optional face workflows with InsightFace
- real-time event delivery to the frontend

## Architecture Direction

Build this as a small set of services:

1. `services/control-api`
2. `services/vision`
3. `services/agent`

Do not split every model into its own network service yet. Instead, implement a modular pipeline inside `services/vision` with adapter interfaces for:

- detector
- embedding model
- face model
- VLM model

## Suggested Backend Stack

Use:

- Python
- FastAPI
- Pydantic
- Postgres
- Redis
- MinIO
- MediaMTX for stream relay
- FFmpeg or PyAV for frame extraction and clip processing

Use `pgvector` inside Postgres if you need semantic search later. Do not add a separate vector database yet.

## Core Domain Areas

Implement API and data models for:

- sites
- cameras
- streams
- detections
- alerts
- incidents
- evidence clips
- operator notes
- audit logs

## Vision Pipeline Requirements

The `vision` service should support this pipeline:

1. ingest frames from camera streams or sample files
2. run object detection
3. optionally crop and classify or embed detections
4. optionally run face analysis when enabled
5. optionally run VLM summarization when enabled and hardware allows
6. persist structured events and thumbnails
7. publish alert-worthy events to the API layer

Make model stages configurable per camera or per policy.

## Model Strategy

Use a pluggable model configuration rather than hard-coding one stack forever.

Baseline expectations:

- detector: start with a well-supported open-source detector
- embeddings: MobileCLIP or an equivalent lightweight image-text embedding model
- face: InsightFace as optional and disabled by default
- VLM: optional and disabled by default unless the machine profile enables it

Design the code so CPU mode works for demos and GPU mode can be enabled later through Docker profiles.

## API Requirements

The `control-api` service should expose:

- REST APIs for CRUD and search
- WebSocket or SSE for live alerts, health, and job state
- typed schemas shared with the frontend

The API must support:

- camera health status
- recent detections
- incident creation and review
- playback metadata lookup
- evidence export job tracking

## Storage Requirements

- Postgres for relational metadata
- Redis for cache, transient jobs, and pub-sub style coordination
- MinIO for thumbnails, clips, and evidence packages

## Delivery Requirements

- provide a sample-data path so the system can run without real RTSP cameras
- make real camera support a first-class path, not an afterthought
- keep the backend observable with health endpoints and structured logs

## Deliverables

- service scaffolds for `control-api` and `vision`
- initial database schema or migrations
- sample frame or clip ingestion path
- one end-to-end detection-to-alert flow
- API contracts that the React frontend can consume

## Acceptance Criteria

- the system can ingest demo media and produce structured detections
- detections can become alerts and incidents
- the frontend has stable APIs to integrate against
- optional models can be toggled without redesigning the whole backend
- the architecture is realistic for an open-source Docker deployment on a single machine

