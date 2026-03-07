# Repository Architecture

This monorepo is organized around a single product surface (video operations console) with clear boundaries for backend and AI services that will evolve later.

## Layout

- `apps/web`: React operator console for live monitoring, alert triage, incidents, playback, and future agent chat.
- `packages/types`: Shared TypeScript domain models and API DTOs.
- `packages/api-client`: Typed adapters that hide data sources (mock now, backend later).
- `packages/ui`: Shared UI primitives and domain components reused by pages.
- `services/control-api`: FastAPI control plane scaffold with auth validation, approval examples, and room for the main VMS APIs.
- `services/vision`: FastAPI vision scaffold with demo pipeline endpoints and room for full ingest + model inference workflows.
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
3. Add `services/agent` after the authenticated API surface and approval hooks are stable.
4. Add advanced Compose profiles for CPU inference, GPU inference, and local NVR mode after the core path boots cleanly.

This keeps the runtime model realistic early without forcing every inner-loop edit to happen inside a container.

## Deployment Modes

Plan for two ingest and recording modes from the start:

- External NVR/VMS integration: treat third-party NVRs as systems of record when they already own retention, playback, and export. Qaongdur should sync camera inventory, health, events, and playback references through adapter modules instead of forcing full migration.
- Camera-direct local NVR: when a site only has IP cameras and no upstream NVR, Qaongdur should provide a lightweight local NVR path. MediaMTX relays streams, the backend records rolling segments and event clips, Postgres indexes playback metadata, and object storage keeps retained footage and evidence artifacts.

## Storage Direction

- Keep recording storage behind an S3-compatible adapter rather than hard-coding one product.
- MinIO remains the default self-hosted option for local development and first public releases.
- RustFS can be used as the object-storage backend for a local Qaongdur NVR deployment because the storage role is S3-compatible blobs for segments, clips, thumbnails, and exports.
- Do not treat RustFS as the NVR itself. Qaongdur still needs recording, retention, playback indexing, and clip-export logic above the object store.
