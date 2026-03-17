# Docker And Machine Onboarding

## Live Rollout Snapshot On 2026-03-17

This doc is no longer only a proposed layout. A first live remote worker rollout was validated against `ati-local-home`.

Validated shape:

- central host runs `vision-api` with `infra/docker/compose.core.yml` plus `infra/docker/compose.distributed-central.yml`
- remote host `ati-local-home` runs `vision-worker` from `infra/docker/compose.worker.yml`
- central LAN endpoint used by the remote worker during validation: `192.168.1.174`
- remote working directory: `/home/ati/works/qaongdur-worker-test/Qaongdur`

Observed live status during verification:

- authenticated `GET /api/v1/vision/crop-tracks` through `control-api` returned distributed crop-track rows and crop image payloads again
- the crop gallery now surfaces those results by default because the page window was widened to 24 hours
- `GET /api/v1/analytics/workers` returned healthy workers on node `ati-local-home`
- `GET /api/v1/analytics/queues` showed the historical backlog still draining on `vision.cpu.face` while newly queued work lands on `vision.cpu`
- remote worker logs showed successful registration, heartbeats, task receipt, Qdrant writes, `/results`, and final `/status` callbacks
- the remote detector runtime was verified on `cuda:0`
- live `nvidia-smi` samples showed the RTX 3060 in use while remote jobs were running
- the older sampler path produced `framesDecoded=900` and `framesSampled=450` on a 60 second segment
- the Compose-managed worker on `ati-local-home` then produced `framesDecoded=900` and `framesSampled=600` on a comparable 60 second segment, which is the expected result for a 10 FPS target on a 15 FPS recording

Current rollout caveats:

- the remote workers are intentionally running with `VISION_FACE_ENABLED=false`
- the central stack now also runs with `VISION_FACE_ENABLED=false`, so new jobs route to `vision.cpu`, but the old `vision.cpu.face` backlog is still present
- `vision-api` is still using SQLite in `/data/vision.sqlite3`
- historical `vision.local` rows from the old local path still show up in queue summaries
- the central `vision-api` process still shows meaningful CPU usage during distributed work because scan, upload, and result-ingest duties remain centralized
- the scanner now skips re-hashing already-uploaded queued or processed segments and safely skips files that disappear during discovery, but a backlog of older pending recordings still keeps the central CPU above the final target

## Commands Used For The First Live Rollout

### Central host

```bash
docker compose \
  --env-file .env \
  -f infra/docker/compose.core.yml \
  -f infra/docker/compose.distributed-central.yml \
  --profile core \
  --profile mock-video \
  --profile vision-api \
  up -d --build
```

### Remote worker host

The repo was synced to:

```text
/home/ati/works/qaongdur-worker-test/Qaongdur
```

The worker env file used:

```text
/home/ati/works/qaongdur-worker-test/Qaongdur/.env.worker
```

The worker runtime was then moved to:

- `VISION_SAMPLE_FPS=10.0`
- `VISION_MAX_SAMPLE_FPS=10.0`
- `VISION_DETECTOR_DEVICE=cuda:0`
- `VISION_EMBEDDING_DEVICE=cuda:0`
- `VISION_CONTAINER_RUNTIME=nvidia`
- `VISION_TORCH_INDEX_URL=https://download.pytorch.org/whl/cu121`

The worker image was loaded from the already-built local image, then started with:

```bash
docker compose \
  --env-file .env.worker \
  -f infra/docker/compose.worker.yml \
  up -d vision-worker
```

During live validation, one additional one-off worker was started with `PYTHONPATH=/app/src` so the mounted source tree could be used immediately for sampler verification before the long-running service worker was rotated:

```bash
docker compose \
  --env-file .env.worker \
  -f infra/docker/compose.worker.yml \
  run -d --no-deps \
  -e PYTHONPATH=/app/src \
  -e QAONGDUR_VISION_WORKER_NAME=vision-worker-src \
  vision-worker
```

That one-off worker was only used as an intermediate verification step. The steady-state worker was then rotated back to the Compose-managed `vision-worker` service, and that service container completed a real job with `framesSampled=600`.

The remote image was sanity-checked before Compose startup with:

```bash
docker run --rm qaongdur-vision-runtime:distributed-dev python -V
docker run --rm qaongdur-vision-runtime:distributed-dev \
  python -c "import vision_service.main_worker as m; print('worker-import-ok')"
```

## Central Compose Changes

Keep the existing core stack, but add distributed profiles and services.

## Service Additions

Add these services to the central runtime:

- `vision-api`
- `recording-sync`
- optional `flower` for Celery inspection

Keep these existing central services:

- `control-api`
- `postgres`
- `redis`
- `object-storage`
- `mediamtx`
- `qdrant`
- `keycloak`

Remove the assumption that the central `vision` container also owns all processing.

## Suggested Compose Profiles

- `core`
- `vision-api`
- `recording-sync`
- `vision-worker-cpu`
- `vision-worker-gpu`
- `face`
- `distributed-mock`

## Recommended Compose File Split

Keep the existing `infra/docker/compose.core.yml`, but add:

- `infra/docker/compose.distributed-central.yml`
- `infra/docker/compose.worker.yml`

### `compose.distributed-central.yml`

Should define:

- `vision-api`
- `recording-sync`
- optional `flower`

### `compose.worker.yml`

Should define:

- `vision-worker`
- optional `face-api`

This keeps the worker host bootstrap independent from the full central stack.

## Environment Variables To Add

### Shared

- `VISION_EXECUTION_MODE=central|worker`
- `VISION_QUEUE_BROKER_URL=redis://redis:6379/0`
- `VISION_QUEUE_RESULT_BACKEND=redis://redis:6379/1`
- `VISION_POSTGRES_DSN=postgresql://...`
- `VISION_OBJECT_STORAGE_ENDPOINT=http://object-storage:9000`
- `VISION_OBJECT_STORAGE_BUCKET=qaongdur-dev`
- `VISION_QDRANT_URL=http://qdrant:6333`

### Central-only

- `VISION_SEGMENT_UPLOAD_ENABLED=true`
- `VISION_SEGMENT_SOURCE_DIR=/recordings`
- `VISION_SEGMENT_POLL_INTERVAL_SECONDS=10`
- `VISION_JOB_DEFAULT_QUEUE=vision.cpu`
- `VISION_JOB_FACE_QUEUE=vision.cpu.face`
- `VISION_WORKER_OFFLINE_TIMEOUT_SECONDS=60`

### Worker-only

- `VISION_WORKER_ID=`
- `VISION_WORKER_NAME=vision-worker-1`
- `VISION_NODE_NAME=ati-local-home`
- `VISION_NODE_SSH_ALIAS=ati-local-home`
- `PYTHONPATH=/app/src`
- `VISION_WORKER_QUEUES=vision.cpu,vision.cpu.face`
- `VISION_WORKER_CAPACITY_SLOTS=1`
- `VISION_REGISTER_URL=http://vision-api:8010/api/v1/internal/analytics/workers/register`
- `VISION_HEARTBEAT_URL=http://vision-api:8010/api/v1/internal/analytics/workers/heartbeat`
- `FACE_API_URL=http://face-api:8020`

## Local Multi-Worker Mock

Yes, one machine can mock multiple analytic nodes.

## Option 1: simplest local test

Run multiple worker containers against one central stack.

Example:

```bash
docker compose \
  -f infra/docker/compose.core.yml \
  -f infra/docker/compose.distributed-central.yml \
  -f infra/docker/compose.worker.yml \
  up -d --scale vision-worker=4
```

What this validates:

- queue balancing
- worker registration
- retries
- Qdrant and Postgres write contention

What this does not validate well:

- real network latency between hosts
- different driver states
- different GPU classes

## Option 2: better host simulation

Run one central stack and multiple worker stacks with different env files and container names.

This is the best Docker-only approximation before real remote hosts.

## Face Runtime Placement

For distributed mode, prefer:

- one `face-api` sidecar per worker host

Not:

- one central `face-api` shared by all workers

That keeps face extraction close to the segment processor and reduces network churn.

## Ansible Layout

Add:

```text
ops/ansible/
  inventories/
    dev/
      hosts.yml
  playbooks/
    bootstrap-analytic.yml
    deploy-worker.yml
  roles/
    docker/
    nvidia_toolkit/
    qaongdur_worker/
```

## Example Inventory

```yaml
all:
  children:
    analytics:
      hosts:
        ati-local-home:
          ansible_host: ati-local-home
          qaongdur_node_name: ati-local-home
          qaongdur_worker_queues:
            - vision.cpu
            - vision.cpu.face
          qaongdur_face_enabled: true
          qaongdur_gpu_enabled: false
```

## Bootstrap Responsibilities

### `bootstrap-analytic.yml`

Install:

- Docker Engine
- Docker Compose plugin
- optional NVIDIA Container Toolkit
- worker env file
- worker model cache directories
- systemd unit or Compose project for the worker stack

### `deploy-worker.yml`

Deploy:

- `vision-worker` image
- optional `face-api` image
- updated env vars
- restart policy and health checks

## Worker Host Runtime Shape

Use one dedicated working directory, for example:

```text
/opt/qaongdur-worker/
  .env
  compose.worker.yml
  runtime/
  cache/
  logs/
```

## Initial Docker Health Checks

### `vision-worker`

Check:

- registration succeeded
- heartbeat loop running
- queue broker reachable
- `docker compose ps` shows the worker container as `Up`
- worker logs show task receipt and status callbacks to `vision-api`

### Extra checks that were useful in the live rollout

- `curl http://127.0.0.1:8010/healthz`
- `curl http://127.0.0.1:8010/api/v1/analytics/workers`
- `curl http://127.0.0.1:8010/api/v1/analytics/nodes`
- `curl http://127.0.0.1:8010/api/v1/analytics/queues`
- `ssh ati-local-home 'curl -sf http://192.168.1.174:8010/readyz'`
- `ssh ati-local-home 'curl -sf http://192.168.1.174:6333/'`

### `face-api`

Keep the existing health model, but report bootstrap state clearly so the worker can mark `supportsFace=false` until ready.

## Migration Note

Keep the old single-node `vision-cpu` profile during the transition. Add distributed profiles beside it, then retire the old profile after feature parity is reached.
