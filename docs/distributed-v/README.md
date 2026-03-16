# Distributed Vision Refactor

Concrete planning set for moving Qaongdur from the current single-node recorded-segment processor to a distributed analytics design with remote workers.

## Goal

Keep the current product shape:

- `control-api` remains the main operator-facing control plane
- MediaMTX remains the relay and recorder
- Qdrant remains the vector store
- MinIO remains the default object store

Change the execution model:

- finalized recording segments become portable work items
- analytics workers pull jobs instead of sharing one local `/recordings` volume
- worker onboarding uses `ssh` only for provisioning and bootstrap
- search stays centralized even when inference is distributed

## Primary Decisions

- Use `Celery + Redis` for job dispatch and worker-side pull-based load balancing.
- Keep `control-api`, Postgres, Redis, MinIO, Qdrant, and MediaMTX on the central server.
- Split the current `services/vision` responsibility into an API or scheduler role and a worker role.
- Move vision metadata out of local SQLite and into Postgres.
- Persist frame-based results at sampled-frame granularity, not at native camera FPS.
- Keep Qdrant as the system of record for vectors and store only vector references plus metadata in Postgres.
- Use `Ansible` for analytic-machine installation and onboarding.

## Current Repo Seams This Plan Builds On

- `control-api` already exposes internal vision source discovery through `/api/v1/internal/vision/sources`.
- `services/vision` already has a clear segment-scanning loop and worker loop.
- `services/vision` already models sampled observations in memory.
- `services/vision` already proxies search and crop-track reads through `control-api`.
- `face-api` already exists as a sidecar-shaped boundary and can move to the worker host.

## Doc Map

- [01-target-architecture.md](./01-target-architecture.md): target runtime shape and request flows
- [02-repo-and-service-refactor.md](./02-repo-and-service-refactor.md): concrete service and codebase refactor plan
- [03-data-model.md](./03-data-model.md): new Postgres tables, storage layout, and indexing rules
- [04-queue-and-api-contracts.md](./04-queue-and-api-contracts.md): queue names, payloads, heartbeats, and idempotency rules
- [05-docker-and-machine-onboarding.md](./05-docker-and-machine-onboarding.md): Compose changes, local multi-worker mock, and Ansible onboarding
- [06-rollout-plan.md](./06-rollout-plan.md): staged implementation order and acceptance criteria

## Short Version

Phase 1 should not jump straight to Kubernetes.

Implement this with:

- one central Compose stack
- one worker Compose file for remote analytic hosts
- `Ansible` for bootstrap
- `Celery + Redis` for distributed jobs

After the worker contract, object-storage flow, and health model are stable, the same service boundaries can later move to `k3s`.
