# Codex Prompt: Repository Structure

You are Codex working in a greenfield open-source project. Build the initial repository structure for a Docker-based VMS product with a React frontend, Keycloak authentication, a Python backend, and a future in-app agent/chat layer.

## Primary Goal

Create a monorepo that is easy to understand, easy to run locally, and ready for later GPU-backed AI services without forcing an over-engineered microservice split on day one.

## Architectural Decisions

- Use a monorepo, not multiple repos.
- Use `pnpm` for JavaScript and TypeScript workspaces.
- Use `uv` and `pyproject.toml` for Python services.
- Use a top-level `Makefile` to normalize developer commands.
- Keep vision inference as one modular Python service first. Do not split detector, embedding, face, and VLM into separate deployables yet.
- Reserve `packages/` for shared frontend code and generated API types.
- Reserve `infra/` for Docker Compose, Keycloak realm config, and media infrastructure.

## Target Repository Layout

Create this structure:

```text
apps/
  web/
services/
  control-api/
  vision/
  agent/
packages/
  ui/
  types/
  api-client/
infra/
  docker/
  keycloak/
  mediamtx/
docs/
  codex-prompts/
scripts/
```

## What Each Area Owns

- `apps/web`: React operator console for dashboard, live monitoring, incidents, playback, and chat UI.
- `services/control-api`: Main backend API for cameras, alerts, incidents, playback metadata, users, and real-time events.
- `services/vision`: Ingest orchestration, frame sampling, model execution, embeddings, face pipeline, and optional VLM enrichment.
- `services/agent`: Chat session management, tool calls, approval workflow, and OpenClaw integration adapter.
- `packages/ui`: Shared design system components.
- `packages/types`: Shared TypeScript types, DTOs, and enums.
- `packages/api-client`: Generated or hand-written frontend SDK for the backend API.
- `infra/docker`: Compose files, environment examples, and startup helpers.
- `infra/keycloak`: Realm export, client definitions, theme overrides if needed, and bootstrap notes.
- `infra/mediamtx`: MediaMTX configuration for RTSP/WebRTC/HLS relay.

## Repo Standards

- Add a root `.editorconfig`, `.gitignore`, and `README.md`.
- Add a root `Makefile` with at least `setup`, `dev`, `lint`, `test`, and `docker-up` placeholders.
- Add a root `docs/architecture.md` that explains why the repo is separated this way.
- Add a root `scripts/` folder only for cross-service setup and developer automation.
- Keep environment variables in per-service `.env.example` files plus a short root environment guide.
- Do not add Kubernetes yet. Docker Compose is the default local and demo runtime.

## Non-Goals

- Do not build all application logic yet.
- Do not introduce a service mesh, event platform cluster, or polyrepo CI strategy.
- Do not create separate repos for frontend, AI, and auth.

## Deliverables

- Initial folder tree with placeholder `README.md` files where useful.
- Workspace configuration for `pnpm`.
- Python service scaffolds with `pyproject.toml`.
- Root developer tooling files.
- A short architecture document that justifies the monorepo split.

## Acceptance Criteria

- A new contributor can understand where frontend, backend, auth, and AI code belong in under five minutes.
- The structure leaves room for GPU-heavy features later without forcing an early rewrite.
- Shared types and API clients have a clear home.
- The repo can support open-source contributions without hidden conventions.

