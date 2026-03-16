# Repository Architecture

This monorepo is organized around a single product surface (video operations console) with clear boundaries for backend and AI services that will evolve later.

## Layout

- `apps/web`: React operator console for live monitoring, alert triage, incidents, playback, and future agent chat.
- `packages/types`: Shared TypeScript domain models and API DTOs.
- `packages/api-client`: Typed adapters that hide data sources (mock now, backend later).
- `packages/ui`: Shared UI primitives and domain components reused by pages.
- `services/control-api`: FastAPI control plane service with auth validation, a currently file-backed RTSP camera inventory, MediaMTX path reconciliation, playback search, approval examples, and room for the rest of the VMS APIs.
- `services/vision`: FastAPI vision service that consumes MediaMTX-backed mock-video relay sources, persists tracked crop artifacts, and leaves room for broader live-stream inference workflows.
- `services/face-api`: FastAPI sidecar that bootstraps InspireFace from the vendored `third_party/InspireFace` submodule, hydrates the `Megatron` pack into its runtime volume, and serves crop-level face embeddings to `services/vision`.
- `services/agent`: Planned in-app agent orchestration and tool-calling.
- `infra/docker`, `infra/keycloak`, `infra/mediamtx`: Infrastructure setup areas.

## Why This Split

- Keeps the frontend shippable now while preserving integration seams.
- Avoids early microservice complexity but leaves clean ownership boundaries.
- Makes open-source contribution easier by placing reusable frontend code in `packages/`.
- Supports progressive replacement of mocks with backend APIs without rewriting UI screens.

## Delivery Order

The repo is now explicitly container-first for shared runtime services.

Recommended implementation sequence:

1. Build `services/control-api` and `services/vision` together with the `core` Docker Compose runtime.
2. Use that core runtime to stabilize auth, API contracts, storage dependencies, and service-to-service networking.
3. Add the investigation, identity-search, map, and ROI milestone from `docs/codex-prompts/06-vision-investigation-identity-search-roi.md`.
4. Add `services/agent` after the authenticated API surface, approval hooks, investigation UI, and search surfaces are stable.
5. Add advanced Compose profiles for CPU inference, GPU inference, and local NVR mode after the core path boots cleanly.

This keeps the runtime model realistic early without forcing every inner-loop edit to happen inside a container.

## Deployment Modes

Plan for two ingest and recording modes from the start:

- External NVR/VMS integration: treat third-party NVRs as systems of record when they already own retention, playback, and export. Qaongdur should sync camera inventory, health, events, and playback references through adapter modules instead of forcing full migration.
- Camera-direct local NVR: when a site only has IP cameras and no upstream NVR, Qaongdur should provide a lightweight local NVR path. MediaMTX relays streams, the backend records rolling segments and event clips, Postgres indexes playback metadata, and object storage keeps retained footage and evidence artifacts.

Current implemented slice:

- `control-api` persists camera definitions, supports reconnect and remove actions, and rehydrates missing MediaMTX paths after a relay restart
- camera definitions now carry optional geolocation metadata so mapped cameras can be reviewed spatially before ROI tooling lands
- MediaMTX serves live HLS and playback URLs for recorded spans
- the web console can add RTSP cameras, view live video, and search playback against this local media path
- the Devices page now has an inventory/map split, and the map mode renders geolocated cameras with MapLibre over open raster tiles
- the `mock-streamer` service loops sibling mock videos into MediaMTX as system-managed RTSP cameras, defaulting to one active source on lower-spec dev machines
- the `vision-cpu` profile processes those relay sources from finalized recording chunks, prioritizes newer chunks first, stores first/middle/last track crops, and exposes a crop gallery through `control-api`
- the crop investigation surface already supports paginated track review, start/middle/end source-frame overlays, camera/time pivots, drag-and-drop image queries, and multimodal crop search with face-first image matching
- the crop modal now exposes detected-face and aligned-face previews per qualifying person track so operators can inspect what the face stage actually used
- operator-facing playback and crop search windows now use a configurable timezone preference instead of a fixed UTC-style input flow
- the optional `face-api` sidecar uses the vendored `third_party/InspireFace` submodule and hydrates the `Megatron` pack into its runtime volume for person-track face embeddings
- live Docker verification now confirms semantic text search is working through `POST /api/v1/vision/crop-search` once `vision` is healthy, with result payloads reporting `searchModes=["text"]`

Next planned slice:

- replace the narrow crop-inspection flow with a broader investigation surface
- extend the current crop modal into full investigation workflows, including track-to-subject pivots and richer subject review
- build identity lists, face review, and text/image search hardening over the existing embedding pipeline
- add ROI editing with CVAT-like polygon behavior before agent-chat work

Current known limitation:

- the relay path now supports per-camera RTSP transport selection, but some cameras still need a vendor-specific RTSP path or `rtspAnyPort` compatibility mode before they remain stable
- track metadata stays in the local SQLite store for now, while object and face embeddings are pushed into Qdrant and current crop-vector search queries Qdrant over the filtered track window
- MobileCLIP now initializes lazily on the first semantic-search request instead of during vision-service startup, so default local runtime can leave `VISION_EMBEDDING_ENABLED=true`
- when `VISION_EMBEDDING_ENABLED=false`, crop text search falls back to track metadata ranking instead of true MobileCLIP text-to-image similarity
- the first `face-api` startup compiles InspireFace from source, so face status can remain unavailable for several minutes on a cold boot
- some live `vision/status` payloads still omit `embedding.state` and `embedding.detail`, so the crop-page readiness hint can disagree with the actual semantic-search path
- runtime model assets should be backed up outside Git; see `docs/model-assets.md`

## Task 03 Vision Data Shape

The current Task 03 slice uses file-backed mock videos and stores track artifacts plus metadata locally:

- `video_source`
- `processing_job`
- `track`
- `storage_artifact`
- `track_embedding`
- `track_face_embedding`

This is intentionally shaped so the same entities can migrate into Postgres later without changing the frontend contract.

Future ROI support should stay normalized rather than embedding polygons directly into track rows. The planned direction is:

- `roi_zone`
- `roi_zone_vertex`
- `roi_rule`
- `roi_rule_label_filter`
- `track_roi_intersection`

That will allow per-camera polygon drawing and later filtering for enter, exit, intersect, or dwell logic without rewriting the crop-gallery or detection APIs.

## Storage Direction

- Keep recording storage behind an S3-compatible adapter rather than hard-coding one product.
- The default self-hosted object-storage implementation remains MinIO for local development and first public releases.
- RustFS can be used as the object-storage backend for a local Qaongdur NVR deployment because the storage role is S3-compatible blobs for segments, clips, thumbnails, and exports.
- Do not treat RustFS as the NVR itself. Qaongdur still needs recording, retention, playback indexing, and clip-export logic above the object store.
- In the current local stack, MediaMTX still owns segment recording while a small `recording-pruner` sidecar enforces the test storage budget by deleting the oldest segments once the shared recordings volume exceeds `10 GB`.
