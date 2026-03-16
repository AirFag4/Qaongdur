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
docker compose up -d
```

Hybrid auth-backed host mode:

```bash
cp ../../.env.example ../../.env
cp ../../services/control-api/.env.example ../../services/control-api/.env
cd ../..
docker compose -f infra/docker/compose.auth.yml up -d
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
- when `docker compose up -d` is running, the Crop Gallery reads VMS-backed mock-video sources, jobs, and track cards through `control-api`
- system-managed mock-video cameras from the sibling `../Video` directory appear in the Devices page and cannot be removed from the UI while the mock-video stack is enabled
- alerts and incidents still return placeholder backend responses while the full detection and incident pipeline is being built
- the Devices page exposes reconnect and remove actions only for `site-admin` and `platform-admin`
- the Devices page now supports optional camera geolocation metadata during onboarding and a `Device Map` mode powered by MapLibre with live/playback/crop pivots for mapped cameras
- the Crop Gallery now keeps draft filters locally and runs the query only when `Search Crops` is pressed
- the Crop Gallery is paginated at 20 tracks per page and only loads the representative middle crop for the grid view
- clicking a crop card opens a closable investigation modal that fetches the track detail lazily, including start/middle/end source-frame overlays and direct pivots into live or playback
- the Crop Gallery now accepts `cameraId`, `from`, `to`, `fromAt`, and `toAt` query-parameter pivots so other pages can land operators in a camera-scoped investigation window
- the Crop Gallery top filter form now accepts optional text and image queries; image search tries face-first matching, and combined text+image queries are merged into one ranked result list
- the Settings page now shows the shared local media budget split between playback recordings and crop artifacts, plus the current embedding enabled/disabled state
- the Settings page now also holds the operator timezone preference used by playback and crop search forms
- the Playback page now has its own camera selection controls instead of relying only on the site sidebar
- the app theme toggle label is now explicit as `Theme / Light` or `Theme / Dark`, and the smaller operator panels follow the selected theme instead of staying dark-only

## Build And Lint

```bash
pnpm --filter @qaongdur/web lint
pnpm --filter @qaongdur/web build
```
