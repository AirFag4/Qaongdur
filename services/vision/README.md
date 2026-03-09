# vision

FastAPI vision service for automatic recorded-segment processing, crop persistence, and future AI enrichment stages.

## Local Setup

1. Copy `.env.example` to `.env`.
2. For the lightweight scaffold only, run `uv run qaongdur-vision`.
3. For the full detector and embedder path on the host, install the optional model extras first:

```bash
python -m pip install '.[models]'
uv run qaongdur-vision
```

Container path:

```bash
git submodule update --init --recursive
cp .env.example .env
make vision-up
```

The container path is the recommended way to run the full mock-video slice because it pins CPU-only PyTorch for this profile and starts the paired `mock-streamer` plus `face-api` services.
It installs `supervision` from the vendored `third_party/supervision` submodule, so the tracked runtime is pinned inside the repo.

## Current Endpoints

- `GET /healthz`
- `GET /readyz`
- `GET /api/v1/vision/sources`
- `GET /api/v1/vision/mock-sources`
- `GET /api/v1/vision/status`
- `POST /api/v1/vision/scan`
- `POST /api/v1/vision/mock-jobs/run`
- `GET /api/v1/vision/crop-tracks`
- `GET /api/v1/vision/crop-tracks/{track_id}`

## Current Mock-Video Flow

- input files come from the sibling `Video/` directory mounted at `/mock-videos` in Compose
- `control-api` and `mock-streamer` turn those files into system-managed RTSP cameras under MediaMTX
- the shared dev default limits active mock cameras to `MOCK_VIDEO_MAX_SOURCES=1` so a fresh clone does not try to process every large file at once
- `services/vision` watches finalized MediaMTX chunks under `/recordings` and processes recorded segments instead of reading the file path directly
- each job is bounded to one finalized recording chunk and stores real wall-clock timestamps derived from the chunk start time
- the detector keeps only `person` and `vehicle`
- track association uses `supervision.ByteTrack`
- tracks are sampled at `1-3 fps`, default `2 fps`
- segment scheduling prioritizes newer recorded chunks first, and worker count is configurable through `VISION_SEGMENT_WORKER_COUNT`
- each closed track stores first, middle, and last crop images
- the `/crops` page uses the middle crop as the representative card image and keeps first and last timestamps in metadata
- the `/crops` page hides retired mock-source history by default and exposes an `Include retired history` toggle
- embeddings are computed from crop images only
- face extraction is attempted once per qualifying person track through the separate `face-api` sidecar
- metadata and embeddings are currently persisted in SQLite inside `/data/vision.sqlite3`
- crop artifacts are stored under `/data/artifacts` and pruned against `VISION_STORAGE_LIMIT_BYTES`, default `10 GB`

## Current Limitations

- MobileCLIP2 uses a deterministic histogram fallback when the requested runtime weights are unavailable
- the first `vision` start after rebuilding the image is slower than the earlier scaffold because the full detector, embedder, and tracking dependencies are installed in-container
- the first `face-api` start compiles InspireFace from the vendored `third_party/InspireFace` submodule and may download the `Megatron` pack into `/runtime`, so the face stage can report `service-unreachable` or `service-not-ready` until that bootstrap completes
- clones that skipped submodule initialization must run `git submodule update --init --recursive` before rebuilding the `face-api` or `vision` images
- the job processes the current point in each looping relay, not a hard reset to the exact beginning of the source file
- VLM is skipped
- track metadata is still persisted in the local SQLite store even though object and face embeddings are also upserted into Qdrant
- ROI filtering is a future schema feature, not part of the current processing loop
- historical tracks from retired mock sources remain in the SQLite store until explicit cleanup or `VISION_PURGE_RETIRED_MOCK_HISTORY=true` is enabled
- the default runtime intentionally favors one mock source and one worker unless you raise `MOCK_VIDEO_MAX_SOURCES` or `VISION_SEGMENT_WORKER_COUNT`
- face calls can still time out under heavier load even though the sidecar is healthy
