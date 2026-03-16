# Data Model

## Storage Roles

### Postgres

System of record for:

- workers and nodes
- segment catalog
- jobs and retries
- track summaries
- sampled-frame observations
- face metadata
- artifact references

### Qdrant

System of record for:

- object embedding vectors
- face embedding vectors

### MinIO

System of record for blobs:

- recording segments uploaded from MediaMTX
- crop images
- frame overlays
- face-aligned images

## Replace The Current SQLite Tables

The existing local SQLite tables in `services/vision` should move into Postgres and expand for distributed execution.

## Worker And Node Tables

### `analytic_node`

One row per analytic machine.

Suggested columns:

- `id uuid primary key`
- `name text not null`
- `ssh_alias text unique`
- `hostname text not null`
- `status text not null`
- `drain_mode boolean not null default false`
- `gpu_available boolean not null default false`
- `gpu_name text`
- `docker_version text`
- `nvidia_runtime_version text`
- `last_heartbeat_at timestamptz`
- `first_registered_at timestamptz not null`
- `updated_at timestamptz not null`

### `analytic_worker`

One row per running worker process or container.

Suggested columns:

- `id uuid primary key`
- `node_id uuid not null references analytic_node(id)`
- `worker_name text not null`
- `queue_names_json jsonb not null`
- `status text not null`
- `capacity_slots integer not null default 1`
- `active_jobs integer not null default 0`
- `supports_face boolean not null default false`
- `supports_text_embedding boolean not null default false`
- `supports_image_embedding boolean not null default false`
- `supports_gpu boolean not null default false`
- `face_model text`
- `embedding_model text`
- `detector_model text`
- `last_heartbeat_at timestamptz`
- `registered_at timestamptz not null`
- `updated_at timestamptz not null`

Indexes:

- `(node_id, status)`
- `(last_heartbeat_at desc)`

## Segment Catalog Tables

### `recording_segment`

One row per finalized MediaMTX segment known to the system.

Suggested columns:

- `id uuid primary key`
- `source_id text not null`
- `camera_id text not null`
- `camera_name text not null`
- `path_name text not null`
- `segment_start_at timestamptz not null`
- `segment_end_at timestamptz`
- `duration_sec numeric`
- `byte_size bigint not null`
- `sha256 text`
- `local_path text`
- `object_bucket text not null`
- `object_key text not null`
- `storage_status text not null`
- `processing_status text not null`
- `created_at timestamptz not null`
- `uploaded_at timestamptz`
- `processed_at timestamptz`

Indexes:

- `(source_id, segment_start_at desc)`
- `(processing_status, segment_start_at asc)`
- unique `(object_bucket, object_key)`

## Job Tables

### `vision_job`

One logical unit of work, usually one segment processing request.

Suggested columns:

- `id uuid primary key`
- `job_type text not null`
- `source_id text not null`
- `segment_id uuid references recording_segment(id)`
- `camera_id text not null`
- `required_queue text not null`
- `required_capabilities_json jsonb not null`
- `priority integer not null default 100`
- `status text not null`
- `requested_by text`
- `requested_at timestamptz not null`
- `started_at timestamptz`
- `finished_at timestamptz`
- `assigned_worker_id uuid references analytic_worker(id)`
- `attempt_count integer not null default 0`
- `detail text`

### `vision_job_attempt`

One row per execution attempt.

Suggested columns:

- `id uuid primary key`
- `job_id uuid not null references vision_job(id)`
- `worker_id uuid references analytic_worker(id)`
- `attempt_no integer not null`
- `status text not null`
- `started_at timestamptz not null`
- `finished_at timestamptz`
- `error_code text`
- `error_detail text`
- `metrics_json jsonb`

Indexes:

- `(job_id, attempt_no desc)`
- `(worker_id, started_at desc)`

## Result Tables

### `track`

Summary row for one closed or active track inside one segment.

Suggested columns:

- `id uuid primary key`
- `job_id uuid not null references vision_job(id)`
- `segment_id uuid not null references recording_segment(id)`
- `source_id text not null`
- `site_id text not null`
- `camera_id text not null`
- `camera_name text not null`
- `label text not null`
- `detector_label text not null`
- `first_seen_at timestamptz not null`
- `last_seen_at timestamptz not null`
- `first_frame_index integer not null`
- `last_frame_index integer not null`
- `sample_fps numeric not null`
- `frame_count integer not null`
- `max_confidence numeric not null`
- `avg_confidence numeric not null`
- `embedding_status text not null`
- `face_status text not null`
- `closed_reason text not null`
- `created_at timestamptz not null`

Indexes:

- `(camera_id, last_seen_at desc)`
- `(label, last_seen_at desc)`
- `(segment_id)`

### `track_observation`

One row per sampled frame for one track.

This is the main new table required for frame-level answers.

Suggested columns:

- `id uuid primary key`
- `track_id uuid not null references track(id)`
- `segment_id uuid not null references recording_segment(id)`
- `source_id text not null`
- `camera_id text not null`
- `frame_index integer not null`
- `offset_ms integer not null`
- `captured_at timestamptz not null`
- `confidence numeric not null`
- `bbox_x1 integer not null`
- `bbox_y1 integer not null`
- `bbox_x2 integer not null`
- `bbox_y2 integer not null`
- `point_x integer`
- `point_y integer`
- `crop_artifact_id uuid references storage_artifact(id)`
- `frame_artifact_id uuid references storage_artifact(id)`
- `object_embedding_point_id text`
- `created_at timestamptz not null`

Indexes:

- `(track_id, frame_index asc)`
- `(camera_id, captured_at desc)`
- `(source_id, captured_at desc)`

### `face_observation`

Optional row for face results found within one sampled observation.

Suggested columns:

- `id uuid primary key`
- `observation_id uuid not null references track_observation(id)`
- `track_id uuid not null references track(id)`
- `face_index integer not null default 0`
- `face_confidence numeric`
- `bbox_x1 integer not null`
- `bbox_y1 integer not null`
- `bbox_x2 integer not null`
- `bbox_y2 integer not null`
- `landmarks_json jsonb`
- `aligned_artifact_id uuid references storage_artifact(id)`
- `face_embedding_point_id text`
- `model_name text`
- `status text not null`
- `created_at timestamptz not null`

Indexes:

- `(track_id, created_at desc)`
- `(observation_id)`

### `storage_artifact`

Reference table for all blobs.

Suggested columns:

- `id uuid primary key`
- `owner_type text not null`
- `owner_id uuid not null`
- `source_id text`
- `camera_id text`
- `bucket text not null`
- `object_key text not null`
- `role text not null`
- `mime_type text not null`
- `byte_size bigint not null`
- `sha256 text`
- `width integer`
- `height integer`
- `created_at timestamptz not null`

Indexes:

- `(owner_type, owner_id)`
- unique `(bucket, object_key)`

## Optional Query Tables

### `vision_event`

Use this only if the UI needs a durable event feed beyond track reads.

Suggested use:

- alert candidates
- camera-side processing faults
- worker degradation events

## Qdrant Payload Shape

### Object collection payload

Suggested payload fields:

- `trackId`
- `observationId`
- `segmentId`
- `sourceId`
- `cameraId`
- `label`
- `capturedAt`
- `embeddingKind=object`

### Face collection payload

Suggested payload fields:

- `trackId`
- `observationId`
- `faceObservationId`
- `segmentId`
- `sourceId`
- `cameraId`
- `capturedAt`
- `embeddingKind=face`

## Object Storage Key Shape

### Recording segments

```text
recordings/{site_id}/{camera_id}/{yyyy}/{mm}/{dd}/{segment_id}.mp4
```

### Track crops

```text
artifacts/{track_id}/observations/{observation_id}/crop.jpg
```

### Frame overlays

```text
artifacts/{track_id}/observations/{observation_id}/frame.jpg
```

### Face-aligned images

```text
artifacts/{track_id}/observations/{observation_id}/face/{face_observation_id}/aligned.jpg
```

## Migration Notes

- Migrate the existing `track` and `storage_artifact` concept first.
- Add `track_observation` before changing the UI so new APIs can serve both summary cards and detailed frame-level timelines.
- Keep first or middle or last summary fields in API responses even after full observation storage exists, because the current crop UI benefits from lightweight cards.
