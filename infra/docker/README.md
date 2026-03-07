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
