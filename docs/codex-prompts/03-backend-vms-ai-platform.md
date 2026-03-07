# Codex Prompt: Backend VMS and Vision AI Platform

You are Codex building the first backend for an open-source Docker-based VMS with AI enrichment. Build a practical backend architecture that supports camera inventory, live events, AI detections, incidents, playback metadata, and future agent actions.

## Primary Goal

Create a backend that is demoable early, but structurally ready for:

- object detection
- image and clip embeddings with MobileCLIP
- optional 1B to 2B class VLM enrichment when hardware allows
- optional face workflows with InsightFace
- real-time event delivery to the frontend

## Execution Order

Implement this prompt together with the `core` subset of `docs/codex-prompts/05-docker-open-source-platform.md`.

For this milestone:

- treat container runtime work as part of backend delivery, not as a later packaging pass
- implement `services/control-api` and `services/vision` first
- keep `services/agent` deferred to `docs/codex-prompts/04-agent-chat-openclaw.md`
- do not wait for `vision-gpu` or `nvr-local` profiles before shipping the first backend slice

## Architecture Direction

Build this as a small set of services over time:

1. `services/control-api`
2. `services/vision`
3. `services/agent`

In this prompt's first execution, only `services/control-api` and `services/vision` need to become runnable. `services/agent` should remain a planned downstream consumer of the same auth and API model.

Do not split every model into its own network service yet. Instead, implement a modular pipeline inside `services/vision` with adapter interfaces for:

- detector
- embedding model
- face model
- VLM model
- stream source
- external VMS or NVR connector
- recording storage backend

## Suggested Backend Stack

Use:

- Python
- FastAPI
- Pydantic
- Postgres
- Redis
- MinIO by default, with an S3-compatible storage adapter so RustFS or another compatible store can replace it
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
- recording segments
- retention policies
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
- camera and playback sources that may come from either an external NVR or Qaongdur-managed local recording

## NVR Integration Modes

Support two deployment paths from the first backend iteration:

1. External NVR or VMS mode
2. Camera-direct local NVR mode

For external NVR or VMS mode:

- integrate through adapter modules for vendor APIs, ONVIF discovery, RTSP ingest, or other site-specific connectors
- sync camera inventory, stream endpoints, health, playback handles, and event references
- preserve the external NVR as the recording source of truth when it already manages retention and export well

For camera-direct local NVR mode:

- accept standalone cameras with no upstream NVR
- use MediaMTX for relay and a recorder pipeline in Qaongdur for continuous or policy-based recording
- create rolling recording segments plus event-driven clips
- store playback indexes and retention metadata in Postgres
- store retained segments, thumbnails, and evidence packages in S3-compatible object storage
- expose the same playback and search APIs regardless of whether footage is external or locally recorded

## Storage Requirements

- Postgres for relational metadata
- Redis for cache, transient jobs, and pub-sub style coordination
- S3-compatible object storage for thumbnails, clips, evidence packages, and retained recording segments
- MinIO as the default local deployment target
- RustFS as an acceptable alternative object-storage backend for local NVR deployments when S3 compatibility is sufficient
- implement retention, segment indexing, playback manifests, and export logic in Qaongdur rather than assuming the object store behaves like an NVR

## Delivery Requirements

- provide a sample-data path so the system can run without real RTSP cameras
- make real camera support a first-class path, not an afterthought
- support both external-NVR integrations and camera-only deployments without changing the frontend API contract
- keep the backend observable with health endpoints and structured logs

## Deliverables

- service scaffolds for `control-api` and `vision`
- initial database schema or migrations
- sample frame or clip ingestion path
- one end-to-end detection-to-alert flow
- recording-storage adapter configuration that uses vendor-neutral object-storage settings while defaulting to MinIO and remaining RustFS-compatible
- API contracts that the React frontend can consume

## Acceptance Criteria

- the system can ingest demo media and produce structured detections
- detections can become alerts and incidents
- the frontend has stable APIs to integrate against
- optional models can be toggled without redesigning the whole backend
- a site with cameras but no existing NVR can still be onboarded and recorded locally
- the same playback APIs work for externally managed recordings and Qaongdur-managed local recordings
- the architecture is realistic for an open-source Docker deployment on a single machine
