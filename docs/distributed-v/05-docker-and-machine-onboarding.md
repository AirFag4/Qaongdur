# Docker And Machine Onboarding

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

### `face-api`

Keep the existing health model, but report bootstrap state clearly so the worker can mark `supportsFace=false` until ready.

## Migration Note

Keep the old single-node `vision-cpu` profile during the transition. Add distributed profiles beside it, then retire the old profile after feature parity is reached.
