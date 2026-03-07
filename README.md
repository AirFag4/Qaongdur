# Qaongdur Monorepo

Docker-first VMS + Vision AI + Agent AI project.  
The repo now includes the initial monorepo structure, the first frontend web console, Keycloak-based auth foundations, and the first real backend slice for RTSP camera onboarding, live HLS, and playback search through MediaMTX.

## Quick Start

Fastest UI-only loop:

```bash
pnpm install
pnpm --filter @qaongdur/web dev
```

Current behavior in this mode:

- all operational pages use the in-process mock adapter from `packages/api-client`
- no backend server is required
- auth checks are skipped because Keycloak is not started

Core container runtime:

```bash
cp .env.example .env
make docker-up
make logs
```

Current behavior in this mode:

- Keycloak, control-api, Postgres, Redis, object storage, MediaMTX, and the built web app all run in containers
- auth is real
- camera inventory, device inventory, live tiles, overview metrics, RTSP onboarding, and playback search use the real `control-api`
- site-admin and platform-admin users can reconnect or remove cameras from the Devices page
- MediaMTX records rolling segments and serves playback URLs for finalized recordings
- alerts and incidents are still placeholder backend responses rather than a full detection-to-incident pipeline

Login path in this mode:

- open `http://localhost:5173`
- click `Continue To Keycloak`
- sign in with a seeded user such as `pat.admin` / `ChangeMe123!`

Hybrid host mode with real auth and real auth API, but mock business data in the UI:

```bash
cp .env.example .env
make docker-auth-up
cp apps/web/.env.example apps/web/.env
cp services/control-api/.env.example services/control-api/.env
cd services/control-api && uv run qaongdur-control-api
pnpm --filter @qaongdur/web dev
```

Validation:

```bash
pnpm --filter @qaongdur/web lint
pnpm --filter @qaongdur/web build
python3 -m compileall services/control-api/src services/vision/src
```

## Detailed Change Log

### 1. Repository and Workspace Scaffolding

Added baseline monorepo layout and tooling:

- `apps/web`
- `packages/types`
- `packages/api-client`
- `packages/ui`
- `services/control-api`, `services/vision`, `services/agent`
- `infra/docker`, `infra/keycloak`, `infra/mediamtx`

Added root developer tooling and docs:

- `.editorconfig`, `.gitignore`
- `package.json` + `pnpm-workspace.yaml`
- `Makefile`
- `docs/architecture.md`

### 2. Frontend App (`apps/web`)

Implemented a route-based React console with:

- stack: React + Vite + TypeScript + Tailwind + TanStack Query + TanStack Table + React Hook Form + Zod
- operations-console visual style (dark charcoal surfaces, cyan live accents, amber/red alert semantics)
- pages:
  - Overview dashboard
  - Live monitoring
  - Alerts and events
  - Incident detail
  - Playback and search (timeline layout)
  - Devices inventory
- command palette (`Ctrl/Cmd + K`) with nav + live-grid commands
- keyboard shortcuts:
  - `Alt + 1..6` page navigation
  - `1/4/9/0` live page grid size
- persistent right-side rail reserved for future agent chat + realtime event feed

### 3. Shared Types (`packages/types`)

Defined typed domain contracts for:

- sites, cameras, live tiles, detections
- alerts, incidents, timeline items, evidence clips
- playback segments, devices
- filter DTOs and realtime websocket event types
- `VmsApiClient` interface contract used by the web app

### 4. Typed API Boundary (`packages/api-client`)

Added a mock-backed API layer that is swappable with future backend integration:

- `MockVmsApiClient` implementing `VmsApiClient`
- realistic generated mock datasets for operations workflows
- filtering/search support in alert and playback APIs
- mock websocket abstraction emitting realtime alert/health events

### 5. Shared UI Package (`packages/ui`)

Implemented reusable UI primitives and domain components:

- primitives: `Button`, `Card`, `Badge`, `cn` utility
- shell/navigation: `AppShell`, `SiteCameraSwitcher`
- monitoring: `LiveVideoTile`, `CameraGrid`, `AlertRail`
- incident/evidence: `IncidentSummaryCard`, `EvidenceClipPanel`
- support: `FilterBar`, `HealthStatusBadge`, `EmptyState`, `LoadingState`, `CommandPalette`

### 6. Auth Foundation

Added the first production-oriented auth slice:

- Keycloak realm bootstrap under `infra/keycloak/import`
- local auth compose stack under `infra/docker/compose.auth.yml`
- browser auth integration in `apps/web/src/auth`
- backend JWT validation and role guards in `services/control-api`
- passkey registration and step-up hooks documented in `docs/authentication.md`

### 7. Core Runtime Start

Started the next backend and delivery milestone:

- root `.env.example` for Compose-driven runtime config
- `infra/docker/compose.core.yml` for the `core` stack
- container builds for `apps/web` and `services/control-api`
- initial `services/vision` FastAPI scaffold plus `vision-cpu` profile entry
- MediaMTX config under `infra/mediamtx/mediamtx.yml`
- `make docker-up`, `docker-down`, `logs`, `seed`, and `vision-up`

## For Developers

### Current Frontend Boundaries

- page routing and orchestration live in `apps/web/src`
- domain/UI reuse belongs in `packages/ui`
- all shared domain contracts go in `packages/types`
- all backend integration logic should go through `packages/api-client`
- `packages/api-client/src/index.ts` now uses the real backend when `VITE_CONTROL_API_BASE_URL` is set and only falls back to mocks on network failure for read-only queries

### Current Delivery Order

The roadmap is now container-first for the shared runtime, but host-based inner loops are still acceptable for fast editing.

Recommended next milestone order:

1. `03` backend implementation together with the `core` slice of `05`
2. `04` in-app agent after the shared auth/API/container network is stable
3. advanced `05` profiles for `vision-cpu`, `vision-gpu`, and `nvr-local`

What `03 + core 05` means in practice:

- replace mock client internals with real backend endpoints while preserving the `VmsApiClient` interface
- containerize `web` and `control-api`
- add shared Compose networking for `keycloak`, `postgres`, `redis`, `object-storage`, and `mediamtx`
- ship the first runnable `vision` scaffold even if the full detection-to-alert path is still incomplete
- keep `services/agent` deferred until the authenticated backend surface is stable
- leave advanced GPU and local NVR profiles for a later milestone

### Current Backend Todo

- migrate camera persistence from `/data/cameras.json` to Postgres with real schema migrations
- move playback segment indexing and retention metadata into Postgres instead of relying only on MediaMTX playback listing
- model cameras, devices, sites, and recording metadata as relational entities so inventory, health, and playback can evolve without file-based coordination
- keep MediaMTX as the relay and playback edge, but remove JSON-file state from `control-api` once database-backed persistence is ready

### Planned NVR Direction

- support both external NVR or VMS integrations and camera-direct deployments with no existing NVR
- keep playback and alert APIs consistent whether recordings live in an upstream NVR or in Qaongdur-managed local storage
- use MediaMTX plus Qaongdur recording and indexing logic for the local NVR path
- keep object storage behind an S3-compatible adapter: MinIO is the default implementation today, and RustFS is a viable alternative storage backend rather than the NVR itself

## For AI Coder Tools

### Safe Edit Zones

- UI changes: prefer `packages/ui/src/components/*`
- page behavior/routing: `apps/web/src/{app,pages,components}`
- API behavior: `packages/api-client/src/*`
- domain model updates: `packages/types/src/index.ts`

### Contract Rules

- do not bypass `@qaongdur/api-client` from page components
- keep DTO/shape changes centralized in `@qaongdur/types`
- keep route layout and shell consistency through `OperatorLayout` + `AppShell`
- preserve keyboard shortcut behavior unless explicitly changing UX contracts

### Verification Checklist

Run after edits:

```bash
pnpm --filter @qaongdur/web lint
pnpm --filter @qaongdur/web build
python3 -m compileall services/control-api/src services/vision/src
docker compose --env-file .env.example -f infra/docker/compose.core.yml --profile core config
```

## Keycloak Reset Note

If your local `qaongdur-dev` realm was created before the built-in client scopes were added to `infra/keycloak/import/qaongdur-dev-realm.json`, the web client can receive stripped access tokens that break backend auth.

For a local development reset, recreate the Keycloak data store and let the realm import run again:

```bash
docker compose --env-file .env -f infra/docker/compose.core.yml down
docker volume rm docker_keycloak-postgres-data
make docker-up
```

## RTSP Troubleshooting

If a camera plays for a while and then freezes, check the relay state before assuming the web player is the problem:

```bash
curl -sS -u qaongdur-api:qaongdur-api http://localhost:9997/v3/paths/list
docker compose --env-file .env -f infra/docker/compose.core.yml --profile core logs -f mediamtx
```

Healthy stream indicators:

- `ready=true`
- `tracks` is non-empty
- `bytesReceived` keeps increasing

If the path stays `ready=false`, `tracks=[]`, or MediaMTX logs repeated `request timed out`, the RTSP source is failing upstream of the browser.

Current limitation:

- `control-api` currently programs MediaMTX with RTSP transport forced to `tcp`
- some cameras behave better with `udp` or vendor-specific RTSP paths, so VLC can appear stable while the relay later stalls

If your local `.env` predates the latest Compose changes, refresh it from `.env.example` so keys such as `MEDIAMTX_PLAYBACK_PORT` and the neutral `OBJECT_STORAGE_*` settings are present.

## Planning Docs

Implementation briefs remain under:

1. [`docs/codex-prompts/00-repo-structure.md`](docs/codex-prompts/00-repo-structure.md)
2. [`docs/codex-prompts/01-frontend-web-console.md`](docs/codex-prompts/01-frontend-web-console.md)
3. [`docs/codex-prompts/02-auth-keycloak-passkeys.md`](docs/codex-prompts/02-auth-keycloak-passkeys.md)
4. [`docs/codex-prompts/03-backend-vms-ai-platform.md`](docs/codex-prompts/03-backend-vms-ai-platform.md)
5. [`docs/codex-prompts/04-agent-chat-openclaw.md`](docs/codex-prompts/04-agent-chat-openclaw.md)
6. [`docs/codex-prompts/05-docker-open-source-platform.md`](docs/codex-prompts/05-docker-open-source-platform.md)

Recommended execution order now:

1. [`docs/codex-prompts/03-backend-vms-ai-platform.md`](docs/codex-prompts/03-backend-vms-ai-platform.md) plus the `core` subset of [`docs/codex-prompts/05-docker-open-source-platform.md`](docs/codex-prompts/05-docker-open-source-platform.md)
2. [`docs/codex-prompts/04-agent-chat-openclaw.md`](docs/codex-prompts/04-agent-chat-openclaw.md)
3. advanced profiles and packaging follow-up from [`docs/codex-prompts/05-docker-open-source-platform.md`](docs/codex-prompts/05-docker-open-source-platform.md)
