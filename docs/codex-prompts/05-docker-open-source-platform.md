# Codex Prompt: Docker-Based Open-Source Platform Delivery

You are Codex packaging this project as an open-source Docker-based platform that can run on a developer laptop first and scale up to a stronger GPU workstation later.

## Primary Goal

Create a local-first containerized platform that is easy to clone, boot, and demo.

## Execution Order

Execute this prompt in two stages instead of treating it as one final packaging step.

Stage 1: `core` runtime, done together with `docs/codex-prompts/03-backend-vms-ai-platform.md`

- make Docker Compose the default runtime for shared services immediately
- boot `web`, `control-api`, `keycloak`, `postgres`, `redis`, `object-storage`, and `mediamtx`
- include seed or mock data so the platform is demoable early
- keep `agent`, `vision-cpu`, `vision-gpu`, and `nvr-local` out of the critical path if they are not ready yet

Stage 2: advanced profiles, done after `docs/codex-prompts/06-vision-investigation-identity-search-roi.md` and `docs/codex-prompts/04-agent-chat-openclaw.md`, or when backend surfaces are stable

- add `vision-cpu`
- add `vision-gpu`
- add `nvr-local`
- add any optional `agent` container once the service is real rather than placeholder-only

## Compose Strategy

Use Docker Compose as the primary runtime.

Create profiles for:

- `core`: web app, control API, auth, storage, media relay, and mock or seeded data
- `vision-cpu`: adds CPU inference services
- `vision-gpu`: adds GPU-enabled inference services
- `nvr-local`: enables local recording persistence for sites that have cameras but no upstream NVR

Do not require Kubernetes for the first public version.

## Expected Services

Include or prepare for:

- `web`
- `control-api`
- `vision`
- `agent`
- `postgres`
- `redis`
- `object-storage` in the runtime config, with MinIO as the default image and RustFS as a documented S3-compatible alternative
- `keycloak`
- `mediamtx`

Use healthchecks and persistent named volumes.

For Stage 1, `vision` and `agent` may be absent from the default `core` profile if they are not yet real services. The important requirement is that the `core` profile provides the shared runtime they will later join.

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
- `nvr-local` should make it possible to run Qaongdur as a lightweight local NVR for standalone cameras

Treat the `core` profile as the immediate next milestone. The advanced profiles are follow-up work, not blockers for the first containerized platform release.

## NVR Deployment Modes

- External NVR mode: connect to an existing NVR or VMS, sync cameras and playback references, and avoid duplicating local recording unless explicitly enabled.
- Camera-direct local NVR mode: ingest camera RTSP streams into MediaMTX, record rolling segments, index playback in Postgres, and persist retained segments and evidence in S3-compatible object storage.
- Treat object storage as the recording backend, not as the full NVR. The stack still needs recorder, retention, playback-index, and export components.

## Infrastructure Notes

- Keycloak handles auth
- MediaMTX handles stream relay
- MinIO stores clips and thumbnails by default, and RustFS can fill the same S3-compatible storage role when preferred
- Postgres stores metadata and playback indexes
- Redis coordinates transient work and live state
- local recording requires a recorder or uploader stage in addition to object storage

Keep the compose setup understandable. A new contributor should not need to decode a maze of hidden startup dependencies.

## Deliverables

- `docker-compose.yml` or split compose files with profiles
- Stage 1 first: container build files for `web` and `control-api`
- environment examples
- startup and teardown commands in the root `README.md`
- documented storage configuration for MinIO by default and RustFS as an alternative
- seeded demo path for first-run success

## Acceptance Criteria

- a contributor can clone the repo and start the platform with one documented command path
- the stack is useful in CPU-only mode
- heavier AI features are optional rather than mandatory
- the platform can be deployed either against an external NVR or as a camera-direct local NVR
- the system is clearly structured for open-source contributors
