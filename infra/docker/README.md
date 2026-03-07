# docker

Local Docker assets for the Qaongdur runtime.

## Compose Files

- `compose.auth.yml`: auth-only bootstrap for Keycloak + its Postgres
- `compose.core.yml`: first `core` runtime for web, control-api, auth, storage, and media relay

## Usage

Preferred path from the repo root:

```bash
cp .env.example .env
make docker-up
```

Useful commands:

```bash
make docker-down
make logs
make seed
make vision-up
```

Notes:

- `object-storage-bootstrap` is a one-shot seed job; `Exited (0)` is the expected success state after it creates the bucket
- if you copied `.env` before the object-storage rename, refresh it from `.env.example` or update the storage keys manually
- if your `qaongdur-dev` Keycloak realm was created before the client-scope fix landed, reset `docker_keycloak-postgres-data` and restart so browser tokens include `sub`, roles, and profile claims

## Current Core Services

- `web`
- `control-api`
- `keycloak`
- `keycloak-postgres`
- `postgres`
- `redis`
- `object-storage`
- `object-storage-bootstrap`
- `mediamtx`

The `vision` service is scaffolded and available under the `vision-cpu` profile via `make vision-up`.

## Current Media Slice

The `core` stack now supports a real RTSP media path:

- add an RTSP camera from the Devices page
- `control-api` persists the camera and programs MediaMTX
- live monitoring uses MediaMTX HLS
- playback search returns MediaMTX playback URLs for recorded spans
- stored cameras are rehydrated into MediaMTX after a media-relay restart

MediaMTX records short rolling segments in local development so playback becomes available quickly after ingest starts.
