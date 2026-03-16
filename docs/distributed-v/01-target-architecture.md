# Target Architecture

## Why The Current Shape Needs To Change

Today the repo runs vision as a local service with:

- direct access to the shared `/recordings` volume from MediaMTX
- a local SQLite database inside `services/vision`
- an in-process `PriorityQueue`
- a fixed `QAONGDUR_VISION_SERVICE_URL` from `control-api` to one vision instance

That is a good single-node slice, but it does not support:

- remote analytics machines
- capability-aware scheduling
- worker heartbeats and drain mode
- distributing segment processing across hosts
- a central frame-level result store

## Target Runtime

### Central server

The central host keeps the long-lived stateful services:

- `control-api`
- `vision-api`
- `recording-sync`
- Postgres
- Redis
- MinIO
- Qdrant
- MediaMTX
- Keycloak

### Analytic worker host

Each analytic machine runs:

- `vision-worker`
- optional `face-api` sidecar on the same host
- optional model cache volumes

The worker host does not need direct database ownership. It pulls jobs, processes segments, writes artifacts, and updates central state.

## Service Responsibilities

### `control-api`

Remains the main external API. It should:

- keep camera and operator APIs
- expose analytic-node registration and status endpoints
- proxy read APIs for vision results
- show queue and worker health in the UI

### `vision-api`

This is the new orchestration and query service. It should:

- own the vision metadata schema
- receive segment-ready events from `recording-sync`
- create `vision_job` rows
- route jobs to Celery queues
- expose crop-track, observation, face, and search APIs
- expose worker and queue status APIs for the frontend

### `recording-sync`

This is the bridge from local recorder storage to distributed workers. It should:

- watch finalized MediaMTX segments
- upload finalized segments to MinIO
- write `recording_segment` metadata rows
- mark a segment `ready_for_processing`
- avoid duplicate uploads through content hash or object-key idempotency

### `vision-worker`

This is the distributed execution unit. It should:

- register itself with the central server
- heartbeat its capacity and health
- pull Celery tasks from Redis
- download one segment from MinIO
- run detection, tracking, embedding, and optional face extraction
- write artifacts to MinIO
- write metadata back to Postgres through `vision-api` or direct repository code
- upsert vectors into Qdrant

### `face-api`

Keep it as a worker-local sidecar in phase 1. That keeps:

- face crops local to the worker host
- the heavy InspireFace bootstrap off the central server
- graceful degradation if some workers do not have the face runtime

## Main Flows

## 1. New analytic machine onboarding

1. Operator adds an SSH alias such as `ati-local-home`.
2. Ansible provisions Docker, optional NVIDIA runtime, model-cache directories, and worker env files.
3. The worker stack starts.
4. `vision-worker` registers with `vision-api`.
5. The node appears in the UI as available, degraded, draining, or offline.

## 2. Distributed segment processing

1. MediaMTX closes a recording segment.
2. `recording-sync` uploads the segment to MinIO and writes a `recording_segment` row.
3. `vision-api` creates a `vision_job`.
4. `vision-api` routes the job to a queue such as `vision.cpu` or `vision.gpu.face`.
5. The next compatible worker pulls the task.
6. The worker downloads the segment, processes sampled frames, and persists:
- track summaries
- sampled-frame observations
- face detections
- artifact references
- embedding references
7. The worker marks the job complete or failed.

## 3. Search and review

1. `control-api` continues to proxy operator search requests.
2. `vision-api` reads track and observation metadata from Postgres.
3. `vision-api` reads vector matches from Qdrant.
4. The UI receives central results without needing to know which worker produced them.

## Frame-Level Definition

For this design, frame-based means:

- one persisted row per sampled frame in the vision pipeline
- default sample rate still controlled by `VISION_SAMPLE_FPS`
- not one row per native decoded frame unless a later dense profile enables it

This keeps the result set queryable while still meeting the requirement for bbox and feature data at frame granularity.

## Search Placement

Text and image search should stay centralized in phase 1.

That means:

- workers compute embeddings
- workers push vectors into central Qdrant
- `vision-api` serves text and image search

Do not host a separate search index on every worker at first. That adds synchronization cost and makes ranking consistency harder.

## Future Upgrade Path

Once the worker contract is stable, the same runtime can move to:

- `k3s` for multi-node scheduling
- worker labels for GPU classes
- a DaemonSet-style GPU runtime model

The first implementation should still target Docker Compose because it is easier to debug while the contracts are still moving.
