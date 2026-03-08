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
make face-up
make mock-video-up
```

Notes:

- `object-storage-bootstrap` is a one-shot seed job; `Exited (0)` is the expected success state after it creates the bucket
- if you copied `.env` before the object-storage rename, refresh it from `.env.example` or update the storage keys manually
- if Compose warns that `MEDIAMTX_PLAYBACK_PORT` is unset, your local `.env` is stale and should be refreshed from `.env.example`
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
- `recording-pruner`

The `vision` service is available under the `vision-cpu` profile via `make vision-up`.
The `face-api` service is available under the `face` profile via `make face-up`.
The `mock-streamer` service is available under the `mock-video` profile via `make mock-video-up`.

## Current Media Slice

The `core` stack now supports a real RTSP media path:

- add an RTSP camera from the Devices page
- reconnect or remove a camera from the Devices page as a `site-admin` or `platform-admin`
- `control-api` persists the camera and programs MediaMTX
- live monitoring uses MediaMTX HLS
- playback search returns MediaMTX playback URLs for recorded spans
- stored cameras are rehydrated into MediaMTX after a media-relay restart

MediaMTX records short rolling segments in local development so playback becomes available quickly after ingest starts.
The `recording-pruner` sidecar keeps the `mediamtx-recordings` volume within `RECORDING_STORAGE_LIMIT_BYTES`, default `10 GB`, by deleting the oldest segments first.

## Mock Video Vision

The `vision-cpu` flow now uses the VMS path, not a side-channel file-only path:

- `control-api` discovers `.mp4` files from the sibling `Video/` directory as system-managed cameras
- `mock-streamer` loops those files into MediaMTX as RTSP paths with the configured `MOCK_VIDEO_PATH_PREFIX`
- `vision` reads the MediaMTX relay URL for each source and persists metadata plus crop artifacts in the `vision-data` volume
- `face-api` boots the local InspireFace runtime from the sibling `InspireFace/` checkout and serves crop-level face embeddings to `vision`

Start it with:

```bash
cp .env.example .env
make vision-up
```

Current behavior:

- discovers local `.mp4` sources from `../Video`
- exposes those sources as MediaMTX relay URLs such as `rtsp://mediamtx:8554/mock-video-people-walking`
- samples frames at `VISION_SAMPLE_FPS`, constrained to `1-3 fps`
- detects only `person` and `vehicle`
- stores first, middle, and last crop JPEGs for each closed track
- enforces a `VISION_STORAGE_LIMIT_BYTES` artifact budget, default `10 GB`
- reports detailed face-sidecar state through `VisionPipelineStatus.face`
- skips VLM
- exposes status and crop-track endpoints through `control-api`

Current limitation:

- the first `face-api` startup compiles InspireFace from source and can take several minutes before face status becomes available
- each mock-video job processes the current point in the looping relay for one original file-duration window; it does not restart the publisher from frame zero before every run

## Mock Streamer

For local testing without a physical camera:

```bash
cp .env.example .env
make docker-up
make mock-video-up
```

The mock streamer now prefers real files from `../Video`:

- `people-walking.mp4` becomes `rtsp://mediamtx:8554/mock-video-people-walking`
- `vehicles.mp4` becomes `rtsp://mediamtx:8554/mock-video-vehicles`

If no `.mp4` files are present, it falls back to a looping synthetic test pattern.

Fallback onboarding URL:

- `rtsp://mediamtx:8554/mock-demo`

Configurable `.env` keys:

- `MOCK_VIDEO_PATH_PREFIX`
- `MOCK_STREAM_PATH`
- `MOCK_STREAM_WIDTH`
- `MOCK_STREAM_HEIGHT`
- `MOCK_STREAM_FPS`
- `MOCK_STREAM_BITRATE`

## RTSP Troubleshooting

Check live path state:

```bash
curl -sS -u qaongdur-api:qaongdur-api http://localhost:9997/v3/paths/list
```

Useful signals:

- `ready=true` means MediaMTX currently has stream tracks and can serve the path
- `tracks=[]` plus `bytesReceived=0` means the source is configured but not actually delivering media
- a rising `bytesReceived` counter means the upstream RTSP source is still flowing

Watch relay logs:

```bash
docker compose --env-file .env -f infra/docker/compose.core.yml --profile core logs -f mediamtx
```

Common local failure shape:

- the camera IP is reachable
- TCP `554` opens
- but MediaMTX logs `request timed out` and the path never becomes ready

That usually means the saved RTSP URL, credentials, or transport mode is wrong for that device. Current limitation: `control-api` programs MediaMTX with RTSP transport forced to `tcp`, so cameras that only behave well with `udp` can appear fine in VLC and then stall in the relay.
