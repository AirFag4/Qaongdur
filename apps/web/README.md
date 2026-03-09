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
- the right-rail realtime feed uses mock events only in UI-only mode; when the web app points at the real backend, fake events are disabled until backend event streaming exists
- with a configured backend, camera inventory, live tiles, overview, playback search, and devices come from `control-api`
- camera create, reconnect, and remove actions go directly to `control-api`
- when `make vision-up` is running, the Crop Gallery reads VMS-backed mock-video sources, jobs, and track cards through `control-api`
- system-managed mock-video cameras from the sibling `../Video` directory appear in the Devices page and cannot be removed from the UI while the mock-video stack is enabled
- alerts and incidents still return placeholder backend responses while the full detection and incident pipeline is being built
- the Devices page exposes reconnect and remove actions only for `site-admin` and `platform-admin`
- the Crop Gallery now keeps draft filters locally and runs the query only when `Search Crops` is pressed
- the Crop Gallery is paginated at 20 tracks per page and only loads the representative middle crop for the grid view
- clicking a crop card opens a closable investigation modal that fetches the track detail lazily, including start/middle/end source-frame overlays and direct pivots into live or playback
- the Playback page now has its own camera selection controls instead of relying only on the site sidebar

## Build And Lint

```bash
pnpm --filter @qaongdur/web lint
pnpm --filter @qaongdur/web build
```
