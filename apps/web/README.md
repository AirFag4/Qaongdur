# web

React operator console for Qaongdur.

## Local Paths

Fastest host loop:

```bash
pnpm --filter @qaongdur/web dev
```

If `VITE_CONTROL_API_BASE_URL` is not configured, this uses the in-browser `mockApiClient`, so no API server is required.

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

- UI-only mode remains fully mock-backed
- Keycloak browser auth is live
- control-api auth validation is live
- with a configured backend, camera inventory, live tiles, overview, playback search, and devices come from `control-api`
- camera create, reconnect, and remove actions go directly to `control-api`
- alerts and incidents still return placeholder backend responses while the full detection and incident pipeline is being built
- the Devices page exposes reconnect and remove actions only for `site-admin` and `platform-admin`

## Build And Lint

```bash
pnpm --filter @qaongdur/web lint
pnpm --filter @qaongdur/web build
```
