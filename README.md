# Qaongdur Monorepo

Docker-first VMS + Vision AI + Agent AI project.  
This commit establishes the initial monorepo structure and completes the first full frontend web console implementation with typed mock APIs.

## Quick Start

```bash
pnpm install
pnpm --filter @qaongdur/web dev
```

Validation:

```bash
pnpm --filter @qaongdur/web lint
pnpm --filter @qaongdur/web build
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

## For Developers

### Current Frontend Boundaries

- page routing and orchestration live in `apps/web/src`
- domain/UI reuse belongs in `packages/ui`
- all shared domain contracts go in `packages/types`
- all backend integration logic should go through `packages/api-client`

### Expected Next Steps

- replace mock client internals with real backend endpoints while preserving the `VmsApiClient` interface
- connect auth/session flow (Keycloak docs already in `docs/codex-prompts/02-auth-keycloak-passkeys.md`)
- add pagination/server-side filtering strategies on alerts/devices once API is available
- move websocket mock to real event stream transport

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
```

## Planning Docs

Implementation briefs remain under:

1. [`docs/codex-prompts/00-repo-structure.md`](docs/codex-prompts/00-repo-structure.md)
2. [`docs/codex-prompts/01-frontend-web-console.md`](docs/codex-prompts/01-frontend-web-console.md)
3. [`docs/codex-prompts/02-auth-keycloak-passkeys.md`](docs/codex-prompts/02-auth-keycloak-passkeys.md)
4. [`docs/codex-prompts/03-backend-vms-ai-platform.md`](docs/codex-prompts/03-backend-vms-ai-platform.md)
5. [`docs/codex-prompts/04-agent-chat-openclaw.md`](docs/codex-prompts/04-agent-chat-openclaw.md)
6. [`docs/codex-prompts/05-docker-open-source-platform.md`](docs/codex-prompts/05-docker-open-source-platform.md)
