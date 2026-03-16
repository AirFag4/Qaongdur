# Repo And Service Refactor

## Refactor Goal

Change the current single `services/vision` process into clear runtime roles without forcing a full repo rewrite.

## Recommended Repo Shape

Keep `services/vision` as the shared Python home for vision logic, but split it into explicit roles:

```text
services/
  vision/
    src/vision_service/
      api/
      scheduler/
      worker/
      shared/
      main_api.py
      main_worker.py
  recording-sync/
    src/recording_sync/
      main.py
  face-api/
  control-api/
ops/
  ansible/
    inventories/
    playbooks/
    roles/
```

This is lower churn than creating many new Python packages immediately.

## Runtime Services To Add

### `vision-api`

Build from `services/vision`, but run the API and scheduling path only.

New responsibilities:

- source sync
- segment-ready intake
- job creation
- queue routing
- read APIs
- search APIs
- worker registration and status APIs

### `vision-worker`

Also build from `services/vision`, but run a worker entrypoint only.

New responsibilities:

- Celery worker boot
- machine capability probe
- worker registration and heartbeat
- segment processing
- artifact upload
- Qdrant upsert

### `recording-sync`

New small Python service.

Responsibilities:

- watch local MediaMTX recordings
- upload finalized segments to object storage
- write `recording_segment` rows
- emit or request job creation

## Existing Code To Refactor

## `services/vision/src/vision_service/pipeline.py`

Split the current class into:

- `SegmentCatalogScanner`
- `VisionJobScheduler`
- `SegmentProcessor`
- `SearchService`

Move worker-only code out of API startup so one API container does not initialize detector, embedder, or face runtime unnecessarily.

## `services/vision/src/vision_service/database.py`

Replace SQLite-focused repository code with:

- shared repository interfaces
- Postgres implementation for central metadata
- optional thin local cache only if startup performance needs it later

## `services/vision/src/vision_service/main.py`

Split into:

- `main_api.py`
- `main_worker.py`

Keep `main.py` as a compatibility wrapper only during migration if needed.

## `services/control-api`

Extend `control-api` instead of bypassing it.

Add new proxy routes for:

- analytic nodes
- analytic workers
- queue depth
- segment progress
- observation detail

Add new internal routes only for service-to-service use when necessary.

## `services/face-api`

Phase 1 change:

- deploy it beside `vision-worker`
- stop treating it as a single central sidecar

The code can stay in the same repo folder.

## New Modules To Add Under `services/vision`

### `shared/worker_capabilities.py`

Capability model for:

- GPU presence
- CUDA runtime
- face runtime availability
- MobileCLIP availability
- queue subscriptions
- worker slot count

### `shared/job_models.py`

Pydantic models for:

- `ProcessSegmentTask`
- `BackfillEmbeddingTask`
- `RetryFaceTask`
- `WorkerHeartbeat`
- `WorkerRegistration`

### `scheduler/router.py`

Queue routing rules based on:

- required models
- camera policy
- worker capabilities
- retry class

### `worker/processor.py`

Worker-side processing path that:

- downloads segment objects from MinIO
- runs detection and tracking
- persists `track` plus `track_observation`
- extracts face results
- uploads artifacts
- writes vector references

### `api/search.py`

Central query path for:

- crop-track queries
- observation queries
- text search
- image search
- per-track face detail

## Commands To Add

Add console scripts:

- `qaongdur-vision-api`
- `qaongdur-vision-worker`
- `qaongdur-recording-sync`

Keep the existing `qaongdur-vision` command only as a local dev wrapper during the migration window.

## Control Plane API Additions

Add authenticated external routes in `control-api`:

- `GET /api/v1/analytics/nodes`
- `GET /api/v1/analytics/workers`
- `GET /api/v1/analytics/queues`
- `GET /api/v1/vision/tracks/{trackId}/observations`
- `GET /api/v1/vision/observations/{observationId}`

Add internal service routes in `vision-api`:

- `POST /api/v1/internal/analytics/workers/register`
- `POST /api/v1/internal/analytics/workers/heartbeat`
- `POST /api/v1/internal/recordings/segments`
- `POST /api/v1/internal/vision/jobs`
- `POST /api/v1/internal/vision/jobs/{jobId}/status`

## Suggested PR Sequence

1. Add Postgres schema and repositories while keeping the current single-node runtime alive.
2. Add `recording-sync` and object-storage-backed segments.
3. Add `vision-worker` entrypoint and queue contracts.
4. Move current segment processing out of API startup.
5. Add worker registration, heartbeats, and status APIs.
6. Move `face-api` to worker-local deployment.
7. Remove the old SQLite plus local `/recordings` processing assumption from the normal runtime.
