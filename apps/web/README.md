# web

React operator console for Qaongdur.

## Local Paths

Fastest host loop:

```bash
pnpm --filter @qaongdur/web dev
```

This is still the default mock-data path. The page layer uses the in-browser `mockApiClient`, so no API server is required for dashboard, alerts, incidents, playback, and device screens.

Containerized runtime:

```bash
cp ../../.env.example ../../.env
cd ../..
make docker-up
```

Hybrid auth-backed host mode:

```bash
cp ../../.env.example ../../.env
cp .env.example .env
cp ../../services/control-api/.env.example ../../services/control-api/.env
cd ../..
make docker-auth-up
cd services/control-api && uv run qaongdur-control-api
pnpm --filter @qaongdur/web dev
```

## Current Integration Mode

- primary product UI is fully implemented with realistic mock data
- Keycloak browser auth is live
- control-api auth validation is live
- main VMS data routes still use the typed mock adapter while the backend domain APIs are being built

## Build And Lint

```bash
pnpm --filter @qaongdur/web lint
pnpm --filter @qaongdur/web build
```
