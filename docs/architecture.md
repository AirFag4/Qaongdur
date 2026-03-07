# Repository Architecture

This monorepo is organized around a single product surface (video operations console) with clear boundaries for backend and AI services that will evolve later.

## Layout

- `apps/web`: React operator console for live monitoring, alert triage, incidents, playback, and future agent chat.
- `packages/types`: Shared TypeScript domain models and API DTOs.
- `packages/api-client`: Typed adapters that hide data sources (mock now, backend later).
- `packages/ui`: Shared UI primitives and domain components reused by pages.
- `services/control-api`: Placeholder for the VMS control plane API.
- `services/vision`: Placeholder for ingest + model inference workflows.
- `services/agent`: Placeholder for in-app agent orchestration and tool-calling.
- `infra/docker`, `infra/keycloak`, `infra/mediamtx`: Infrastructure setup areas.

## Why This Split

- Keeps the frontend shippable now while preserving integration seams.
- Avoids early microservice complexity but leaves clean ownership boundaries.
- Makes open-source contribution easier by placing reusable frontend code in `packages/`.
- Supports progressive replacement of mocks with backend APIs without rewriting UI screens.
