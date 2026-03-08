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

The container path is the recommended way to run the full mock-video slice because it pins CPU-only PyTorch for this profile.

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
- the detector keeps only `person` and `vehicle`
- tracks are sampled at `1-3 fps`, default `2 fps`
- each closed track stores first, middle, and last crop images
- embeddings are computed from crop images only
- face extraction is attempted once per qualifying person track
- metadata and embeddings are currently persisted in SQLite inside `/data/vision.sqlite3`
- crop artifacts are stored under `/data/artifacts` and pruned against `VISION_STORAGE_LIMIT_BYTES`, default `10 GB`

## Current Limitations

- the current mock-video pipeline still analyzes local files directly rather than consuming the same RTSP relay path that MediaMTX uses for live view and recording
- MobileCLIP2 uses a deterministic histogram fallback when the requested runtime weights are unavailable
- the face stage reports `unavailable` when the local InspireFace runtime is not packaged with native assets; the checked-out repo needs a built `libInspireFace.so` bundle before it can run on Linux x64
- the current face hook still needs to switch to a recognition-oriented `Megatron` runtime path
- VLM is skipped
- the embedding store is not a full vector index yet; it is shaped for a later Postgres plus `pgvector` migration
- ROI filtering is a future schema feature, not part of the current processing loop
