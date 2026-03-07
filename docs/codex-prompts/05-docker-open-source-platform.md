# Codex Prompt: Docker-Based Open-Source Platform Delivery

You are Codex packaging this project as an open-source Docker-based platform that can run on a developer laptop first and scale up to a stronger GPU workstation later.

## Primary Goal

Create a local-first containerized platform that is easy to clone, boot, and demo.

## Compose Strategy

Use Docker Compose as the primary runtime.

Create profiles for:

- `core`: web app, API, auth, storage, and mock data
- `vision-cpu`: adds CPU inference services
- `vision-gpu`: adds GPU-enabled inference services

Do not require Kubernetes for the first public version.

## Expected Services

Include or prepare for:

- `web`
- `control-api`
- `vision`
- `agent`
- `postgres`
- `redis`
- `minio`
- `keycloak`
- `mediamtx`

Use healthchecks and persistent named volumes.

## Environment and DX Requirements

- provide a root `.env.example`
- provide per-service environment examples where needed
- document the minimum local prerequisites
- add `make` targets for `docker-up`, `docker-down`, `logs`, and `seed`
- make the default path work with demo media and mocked cameras

## Open-Source Readiness

- avoid proprietary managed services in the default setup
- keep ports, volumes, and environment variables documented
- include a short contributor onboarding section
- prefer reproducible container builds

## Runtime Expectations

- `core` profile should boot the UI with mocked or seeded data
- `vision-cpu` should run a basic end-to-end detection flow on a normal machine
- `vision-gpu` should enable optional heavier models without changing app code

## Infrastructure Notes

- Keycloak handles auth
- MediaMTX handles stream relay
- MinIO stores clips and thumbnails
- Postgres stores metadata
- Redis coordinates transient work and live state

Keep the compose setup understandable. A new contributor should not need to decode a maze of hidden startup dependencies.

## Deliverables

- `docker-compose.yml` or split compose files with profiles
- container build files for app services
- environment examples
- startup and teardown commands in the root `README.md`
- seeded demo path for first-run success

## Acceptance Criteria

- a contributor can clone the repo and start the platform with one documented command path
- the stack is useful in CPU-only mode
- heavier AI features are optional rather than mandatory
- the system is clearly structured for open-source contributors

