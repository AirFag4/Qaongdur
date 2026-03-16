# Qaongdur Next Todo

Near-term follow-up items after the current recorded-chunk vision slice.

## Current Milestone

- The next major feature wave is planned in `docs/codex-prompts/06-vision-investigation-identity-search-roi.md`.
- Agent-chat work stays downstream of that milestone.

## Runtime Stability

- Reduce or eliminate `face-api` timeout failures under processing load.
- Fix the `GET /api/v1/vision/status` embedding contract gap so `embedding.enabled`, `embedding.state`, and `embedding.detail` always match the real semantic-search runtime.
- Add a retry or backfill path for any segments processed while vector storage was degraded before the 512-dimensional fallback alignment.
- Make `VisionSource.processedSegmentCount`, `latestProcessedAt`, and `lastSegmentAt` reflect live progress correctly.
- Add a writable cleanup action for retired mock-source history instead of relying only on the env-backed purge toggle.
- Measure first-query MobileCLIP warm-up latency now that initialization is lazy, and decide whether a background warm-up path is still worth adding.
- Decide whether the detector runtime should also move to a startup-safe lazy path, since `yolov8n.pt` is still initialized during app construction.
- Add a scripted local backup and restore workflow for detector, MobileCLIP, and face resource-pack weights outside Git.

## Throughput

- Add per-source queue caps or fairness rules so one noisy camera cannot flood the backlog.
- Decide whether chunk scheduling should stay newest-first only or become a hybrid of newest-first plus guaranteed source rotation.
- Add progress metrics for queued, running, failed, and completed segment jobs per source.
- Add a cleanup or retention policy for stale segment rows once their source files have been pruned.
- Expose `MOCK_VIDEO_MAX_SOURCES` and `VISION_SEGMENT_WORKER_COUNT` through Settings once runtime writes exist.

## Data And Storage

- Move camera persistence from `/data/cameras.json` into Postgres with migrations.
- Move playback segment indexing and retention metadata into Postgres instead of relying only on MediaMTX listing.
- Complete the Qdrant-first search migration beyond the current filtered-track query path, including backfill/repair tooling for older rows and a decision on whether metadata mirrors should stay in SQLite or move fully into Postgres.
- Decide when retired track history should age out automatically versus staying queryable indefinitely.

## UX

- Show source-level analytic progress in the UI so users can tell which streams are already processed and which are still queued.
- Surface vector-store and face-sidecar degradation clearly in the Settings and crop pages.
- Make recording segment duration and related runtime knobs writable from the Settings page instead of env-only.
- Add source and time summaries to the crop page so active-versus-retired history is easier to reason about at a glance.
- Add a richer search summary so operators can tell whether a crop result came from face-image, object-image, true text embedding, or metadata fallback.
- Add an explicit `embedding status unknown` UI state so missing status fields do not get displayed as if text search were disabled.

## Vision Feature Follow-Ups

- Add ROI definition and filtering to the persisted schema and processing loop.
- Benchmark semantic text-search relevance now that live availability is verified, then tune query summaries and ranking explanation in the UI.
- Extend the new face-debug previews with operator actions, retry/backfill flows, and clearer failure states when the face sidecar is degraded.
- Add identity lists, subject review, and face-match audit actions on top of the current face-first search path.
- Keep VLM disabled until the recorded-chunk path, vector storage, and face reliability are stable.
