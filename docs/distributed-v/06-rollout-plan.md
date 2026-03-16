# Rollout Plan

## Implementation Order

The safest path is to preserve the current product behavior while replacing one assumption at a time.

## Phase 0: schema-first groundwork

Deliver:

- Postgres tables for segments, jobs, workers, tracks, observations, faces, and artifacts
- repository layer for Postgres
- no distributed worker requirement yet

Exit criteria:

- current single-node vision path can write to Postgres
- current crop-track APIs still work

## Phase 1: segment portability

Deliver:

- `recording-sync`
- MinIO-backed finalized segment upload
- `recording_segment` rows with object keys

Exit criteria:

- one finalized segment can be re-processed without local `/recordings` access
- segment upload is idempotent

## Phase 2: worker runtime

Deliver:

- `vision-worker` entrypoint
- Celery broker integration
- worker registration and heartbeat
- `vision.process_segment` task

Exit criteria:

- one remote worker can process a segment end to end
- UI can show worker health

## Phase 3: frame-level persistence

Deliver:

- `track_observation`
- `face_observation`
- new observation read APIs

Exit criteria:

- the UI can fetch bbox and artifact detail for each sampled frame of a track
- search results can anchor to a matched observation

## Phase 4: multi-worker balancing

Deliver:

- multiple workers against one Redis broker
- queue metrics
- retry and lease-timeout handling

Exit criteria:

- jobs spread across multiple workers automatically
- offline workers stop receiving new work
- timed-out jobs are retried safely

## Phase 5: worker-local face runtime

Deliver:

- worker-local `face-api`
- face retry jobs
- capability-aware routing to face-enabled workers

Exit criteria:

- workers without face runtime still process non-face work
- face-enabled workers enrich person observations when available

## Phase 6: machine onboarding automation

Deliver:

- `ops/ansible`
- inventory-driven worker bootstrap
- documented example for adding `ati-local-home`

Exit criteria:

- a new SSH-reachable machine can become an analytic worker from one playbook run

## Phase 7: cleanup

Deliver:

- remove SQLite from the normal distributed path
- retire the old local in-process queue path
- keep only one supported distributed runtime path plus a small local-dev mode

## Acceptance Checklist

- a finalized segment is uploaded once and processed once logically
- multiple workers can pull jobs without manual balancing
- frame-level sampled observations are queryable by track and camera
- face results include face bbox, aligned face artifact, and vector reference
- text and image search still work through one central API
- a worker can go offline without corrupting job state
- a new worker host can be provisioned through SSH automation

## Risks To Watch

- Postgres write volume can rise sharply after adding `track_observation`
- Qdrant point cardinality will increase when moving from track-level to observation-level embeddings
- MinIO object count will rise quickly if every observation writes frame overlays by default
- cold boot time for `face-api` can still be long on new worker hosts

## Mitigations

- keep observation persistence at sampled-frame granularity
- make frame-overlay saving configurable
- use deterministic object keys and point IDs
- support backfill jobs for embeddings and face extraction
- add drain mode before maintenance on a worker host

## First PR Recommendation

If starting implementation next, the best first PR is:

1. add the Postgres schema
2. add the repository layer
3. make the current single-node path write `track` plus `track_observation`

That gives immediate product value and reduces the risk of the later distributed steps.
