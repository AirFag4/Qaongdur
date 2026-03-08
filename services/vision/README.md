# vision

FastAPI vision service for mock-video processing, crop persistence, and future AI enrichment stages.

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
cp .env.example .env
make vision-up
```

The container path is the recommended way to run the full mock-video slice because it pins CPU-only PyTorch for this profile and starts the paired `mock-streamer` plus `face-api` services.

## Current Endpoints

- `GET /healthz`
- `GET /readyz`
- `GET /api/v1/vision/mock-sources`
- `GET /api/v1/vision/status`
- `POST /api/v1/vision/mock-jobs/run`
- `GET /api/v1/vision/crop-tracks`
- `GET /api/v1/vision/pipelines`
- `POST /api/v1/vision/demo/run`

## Current Mock-Video Flow

- input files come from the sibling `Video/` directory mounted at `/mock-videos` in Compose
- `control-api` and `mock-streamer` turn those files into system-managed RTSP cameras under MediaMTX, for example `rtsp://mediamtx:8554/mock-video-people-walking`
- `services/vision` reads the MediaMTX relay URL for each mock source instead of processing the file path directly
- each job is bounded to one original file-duration window even though the publisher loops forever
- the detector keeps only `person` and `vehicle`
- tracks are sampled at `1-3 fps`, default `2 fps`
- each closed track stores first, middle, and last crop images
- embeddings are computed from crop images only
- face extraction is attempted once per qualifying person track through the separate `face-api` sidecar
- metadata and embeddings are currently persisted in SQLite inside `/data/vision.sqlite3`
- crop artifacts are stored under `/data/artifacts` and pruned against `VISION_STORAGE_LIMIT_BYTES`, default `10 GB`

## Current Limitations

- MobileCLIP2 uses a deterministic histogram fallback when the requested runtime weights are unavailable
- the first `face-api` start compiles InspireFace from the local sibling `../InspireFace` checkout, so the face stage can report `service-unreachable` or `service-not-ready` until that build completes
- the current face path depends on the host having the `../InspireFace` checkout available for the sidecar volume mount
- the job processes the current point in each looping relay, not a hard reset to the exact beginning of the source file
- VLM is skipped
- the embedding store is not a full vector index yet; it is shaped for a later Postgres plus `pgvector` migration
- ROI filtering is a future schema feature, not part of the current processing loop
