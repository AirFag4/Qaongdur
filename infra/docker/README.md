# docker

Local Docker assets for the Qaongdur runtime.

## Compose Files

- `compose.auth.yml`: auth-only bootstrap for Keycloak + its Postgres
- `compose.core.yml`: first `core` runtime for web, control-api, auth, storage, and media relay

## Usage

Preferred path from the repo root:

```bash
git submodule update --init --recursive
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
- `mock-streamer`
- `recording-pruner`

The `vision` and `qdrant` services are available under the `vision-cpu` profile via `make vision-up`.
The `face-api` service is available under the `face` profile via `make face-up`.
The `mock-streamer` service now starts with the default `core` stack so local `../Video` clips keep publishing after `make docker-up`.
Use `make mock-video-up` when you want to rebuild or restart only the mock publisher.

## Current Media Slice

The `core` stack now supports a real RTSP media path:

- add an RTSP camera from the Devices page
- choose RTSP transport per camera from the Devices page when the source is transport-sensitive
- reconnect or remove a camera from the Devices page as a `site-admin` or `platform-admin`
- `control-api` persists the camera and programs MediaMTX
- live monitoring uses MediaMTX HLS
- playback search returns browser playback URLs plus downloadable MP4 URLs for recorded spans
- stored cameras are rehydrated into MediaMTX after a media-relay restart

MediaMTX records rolling `60s` segments by default in local development, and the value is now exposed from `.env.example` via `MEDIAMTX_RECORD_SEGMENT_DURATION`.
The `recording-pruner` sidecar keeps the `mediamtx-recordings` volume within `RECORDING_STORAGE_LIMIT_BYTES`, default `10 GB`, by deleting the oldest segments first.

## Mock Video Vision

The `vision-cpu` flow now uses finalized recording chunks from the VMS path:

- `control-api` discovers supported video files from the sibling `Video/` directory as system-managed cameras
- `mock-streamer` loops those files into MediaMTX as RTSP paths with the configured `MOCK_VIDEO_PATH_PREFIX`
- `vision` watches `/recordings`, picks up newly finalized chunks, and processes them once with real wall-clock timestamps
- `vision` installs `supervision` from the vendored `third_party/supervision` submodule and uses `ByteTrack`
- `face-api` boots the vendored InspireFace runtime from the `third_party/InspireFace` submodule, downloads the `Megatron` pack into its runtime volume when needed, and serves crop-level face embeddings to `vision`
- `qdrant` stores object and face embeddings from the processed tracks

Start it with:

```bash
cp .env.example .env
make vision-up
```

Current behavior:

- discovers local supported video sources from `../Video`
- caps mock publication to `MOCK_VIDEO_MAX_SOURCES`, default `1`, so lower-spec machines do not try to relay every large file by default
- exposes those sources as MediaMTX relay URLs such as `rtsp://mediamtx:8554/mock-video-people-walking`
- automatically processes finalized recording chunks for current active camera paths that land under `/recordings`
- samples frames at `VISION_SAMPLE_FPS`, constrained to `1-3 fps`
- detects only `person` and `vehicle`
- normalizes looped publishers to the configured `MOCK_STREAM_WIDTH`, `MOCK_STREAM_HEIGHT`, and `MOCK_STREAM_FPS` so larger source files such as 4K vehicle clips stay stable
- queues newer recording chunks ahead of older backlog and exposes `VISION_SEGMENT_WORKER_COUNT` for opt-in parallel workers
- stores first, middle, and last crop JPEGs for each closed track
- uses the middle crop as the representative `/crops` card image while preserving first and last timing metadata plus saved movement points
- enforces a `VISION_STORAGE_LIMIT_BYTES` artifact budget, default `10 GB`
- reports detailed face-sidecar state through `VisionPipelineStatus.face`
- skips VLM
- exposes status, source, crop-track, track-detail, and settings endpoints through `control-api`

Current limitation:

- the first `face-api` startup compiles InspireFace from source and may download the `Megatron` model pack, so it can take several minutes before face status becomes available
- clones that skipped `--recurse-submodules` must run `git submodule update --init --recursive` before building `vision` or `face-api`
- the first `vision` startup after a rebuild is slower than the earlier scaffold because the image now includes packaged tracking, detector, and embedder dependencies
- runtime settings are still env-backed; the Settings page in the web app is a planning surface rather than a live-write control plane today
- retired mock-track history remains in the SQLite store until it is explicitly purged, even though the crop page hides it by default
- the default runtime is intentionally conservative at one mock source and one worker; raise `MOCK_VIDEO_MAX_SOURCES` or `VISION_SEGMENT_WORKER_COUNT` only if the machine can absorb it
- face embedding calls can still time out under heavier processing load

## Mock Streamer

For local testing without a physical camera:

```bash
cp .env.example .env
make docker-up
make mock-video-up
```

The mock streamer now prefers real files from `../Video`:

- supported formats are `.mp4`, `.webm`, `.mkv`, and `.mov`
- once custom files are present, the legacy seed clips (`people-walking.mp4`, `vehicles.mp4`) are skipped automatically
- if the same source exists in multiple containers such as both `.mp4` and `.webm`, only the larger variant is published
- the larger files are preferred first when `MOCK_VIDEO_MAX_SOURCES` limits how many active mock cameras are published
- the generated RTSP path is based on a normalized slug of the source filename

If no supported video files are present, it falls back to a looping synthetic test pattern.

Fallback onboarding URL:

- `rtsp://mediamtx:8554/mock-demo`

Configurable `.env` keys:

- `MOCK_VIDEO_PATH_PREFIX`
- `MOCK_VIDEO_MAX_SOURCES`
- `MOCK_STREAM_PATH`
- `MOCK_STREAM_WIDTH`
- `MOCK_STREAM_HEIGHT`
- `MOCK_STREAM_FPS`
- `MOCK_STREAM_BITRATE`
- `VISION_SEGMENT_WORKER_COUNT`
- `VISION_PURGE_RETIRED_MOCK_HISTORY`

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

That usually means the saved RTSP URL, credentials, or transport mode is wrong for that device.

Current guidance:

- start with `Automatic`
- if the camera returns SDP but TCP setup fails, use `udp`
- if UDP negotiation succeeds but packets still do not arrive, try `rtspAnyPort`
- keep `rtspAnyPort` as a compatibility escape hatch, not the default
