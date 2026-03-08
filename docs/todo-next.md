# Qaongdur Next Todo

Near-term follow-up items after the current recorded-chunk vision slice.

## Runtime Stability

- Fix Qdrant point upserts for both object and face embeddings. The collections are created, but live writes currently return `400 Bad Request`.
- Reduce or eliminate `face-api` timeout failures under processing load.
- Make `VisionSource.processedSegmentCount`, `latestProcessedAt`, and `lastSegmentAt` reflect live progress correctly.
- Add explicit source-retirement handling so old mock sources stop appearing as active inventory once the `Video/` directory changes.

## Throughput

- Replace the current single-worker chunk queue with a bounded multi-worker or per-camera scheduler.
- Prevent large 4K mock streams from starving lower-cost sources in the same queue.
- Add progress metrics for queued, running, failed, and completed segment jobs per source.
- Add a cleanup or retention policy for stale segment rows once their source files have been pruned.

## Data And Storage

- Move camera persistence from `/data/cameras.json` into Postgres with migrations.
- Move playback segment indexing and retention metadata into Postgres instead of relying only on MediaMTX listing.
- Decide whether vector storage remains Qdrant or shifts to `pgvector` once the wider Task 03 schema is ready.
- Add an explicit cleanup path for old track history when the active mock source set is replaced.

## UX

- Show source-level analytic progress in the UI so users can tell which streams are already processed and which are still queued.
- Add filters or toggles to hide retired mock-source history from the crop page.
- Surface vector-store and face-sidecar degradation clearly in the Settings and crop pages.
- Make recording segment duration and related runtime knobs writable from the Settings page instead of env-only.

## Vision Feature Follow-Ups

- Add ROI definition and filtering to the persisted schema and processing loop.
- Add search by embedding once vector storage is healthy.
- Improve face handling so successful face vectors and failures are visible per track.
- Keep VLM disabled until the recorded-chunk path, vector storage, and face reliability are stable.
