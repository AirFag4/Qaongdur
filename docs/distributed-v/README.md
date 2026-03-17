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

## Current Status On 2026-03-17

The first remote analytic machine rollout is live, and the crop-gallery path now works through the distributed stack.

- `vision-api` is running locally from `infra/docker/compose.core.yml` plus `infra/docker/compose.distributed-central.yml`
- `control-api` is now explicitly wired to `vision-api` by `infra/docker/compose.distributed-central.yml`, so `/api/v1/vision/crop-tracks` works again through the authenticated control plane
- the web crop gallery now defaults to a 24 hour window instead of only the last 10 minutes, which exposes the already-produced distributed crop tracks by default
- remote analytic workers on `ati-local-home` are registered, heartbeating, and actively consuming `vision.process_segment` jobs from Redis
- CUDA is verified on the remote RTX 3060 host: the worker container reports `torch.cuda.is_available() == True`, the detector resolves to `cuda:0`, and live `nvidia-smi` samples showed non-zero GPU utilization with about 1.0 to 1.6 GiB of GPU memory in use
- the central scheduler is now issuing jobs at `sampleFps=10.0`
- the old rounded frame-interval sampler was proven to undershoot that target on 15 FPS recordings (`framesDecoded=900`, `framesSampled=450`)
- the Compose-managed worker on `ati-local-home` now imports `/app/src` through `PYTHONPATH=/app/src` and completed a real 60 second job with `framesDecoded=900` and `framesSampled=600`, confirming the timestamp-based sampler reaches the intended 10 FPS target on the steady-state service container
- crop tracks written by distributed jobs are queryable through `control-api` and include `sampleFps: 10.0` plus crop image payloads
- the central stack now has `VISION_FACE_ENABLED=false`, so live status reports the face stage as disabled and newly queued work lands on `vision.cpu`

What is still different from the target:

- metadata is still persisted in the `vision-api` SQLite volume, not Postgres
- segment upload and scan logic currently lives inside `vision-api`; there is no separate `recording-sync` service yet
- face enrichment is still disabled on the live workers (`VISION_FACE_ENABLED=false`)
- historical work already queued on `vision.cpu.face` is still draining from the earlier configuration even though new jobs now route to `vision.cpu`
- old `vision.local` rows from the earlier single-node path still appear in queue status reads
- the central host still does non-trivial work during distributed runs because recording scan, segment upload, result callbacks, and crop persistence still live inside `vision-api`; offload is real, but the main machine is not idle yet
- the `vision-api` scanner now skips re-hashing already-uploaded queued or processed segments and tolerates disappearing files, but the older backlog of pending recordings still keeps central CPU higher than the final target
- `infra/docker/compose.worker.yml` now sets `PYTHONPATH=/app/src` so future Compose worker restarts use the mounted source tree instead of the stale installed package path

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
