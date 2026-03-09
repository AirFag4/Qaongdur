# Qaongdur Next Todo

Near-term follow-up items after the current recorded-chunk vision slice.

## Current Milestone

- The next major feature wave is planned in `docs/codex-prompts/06-vision-investigation-identity-search-roi.md`.
- Agent-chat work stays downstream of that milestone.

## Runtime Stability

- Reduce or eliminate `face-api` timeout failures under processing load.
- Verify Qdrant end-to-end on the live stack after the UUID-based point-id fix, and add a retry or backfill path for any segments processed while vector storage was degraded.
- Make `VisionSource.processedSegmentCount`, `latestProcessedAt`, and `lastSegmentAt` reflect live progress correctly.
- Add a writable cleanup action for retired mock-source history instead of relying only on the env-backed purge toggle.

## Throughput

- Add per-source queue caps or fairness rules so one noisy camera cannot flood the backlog.
- Decide whether chunk scheduling should stay newest-first only or become a hybrid of newest-first plus guaranteed source rotation.
- Add progress metrics for queued, running, failed, and completed segment jobs per source.
- Add a cleanup or retention policy for stale segment rows once their source files have been pruned.
- Expose `MOCK_VIDEO_MAX_SOURCES` and `VISION_SEGMENT_WORKER_COUNT` through Settings once runtime writes exist.

## Data And Storage

- Move camera persistence from `/data/cameras.json` into Postgres with migrations.
- Move playback segment indexing and retention metadata into Postgres instead of relying only on MediaMTX listing.
- Harden Qdrant as the single vector store for object and face search, and decide later only whether its metadata mirrors should stay in SQLite or move fully into Postgres.
- Decide when retired track history should age out automatically versus staying queryable indefinitely.

## UX

- Show source-level analytic progress in the UI so users can tell which streams are already processed and which are still queued.
- Surface vector-store and face-sidecar degradation clearly in the Settings and crop pages.
- Make recording segment duration and related runtime knobs writable from the Settings page instead of env-only.
- Add source and time summaries to the crop page so active-versus-retired history is easier to reason about at a glance.

## Vision Feature Follow-Ups

- Add ROI definition and filtering to the persisted schema and processing loop.
- Add search by embedding once vector storage is healthy.
- Improve face handling so successful face vectors and failures are visible per track.
- Keep VLM disabled until the recorded-chunk path, vector storage, and face reliability are stable.
