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
- `POST /api/v1/vision/crop-search`

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
- `GET /api/v1/vision/crop-tracks` is paginated and returns only the representative middle crop for each card so the gallery stays responsive
- `GET /api/v1/vision/crop-tracks/{track_id}` returns the full first/middle/last crop set plus saved source-frame snapshots and bbox metadata for the investigation modal
- `POST /api/v1/vision/crop-search` accepts the same camera/time/label filters plus optional `textQuery` and `imageBase64`
- image queries try face detection first, search Qdrant across the currently filtered track window when vector storage is available, and fall back to object-crop similarity when no searchable face is found
- combined text and image queries merge both result sets and annotate each returned track with `searchReason` and `searchScore`
- MobileCLIP now initializes lazily on the first image or text embedding request instead of during FastAPI app startup
- once the service is healthy and MobileCLIP has loaded, live text-only crop-search requests return `searchModes=["text"]`
- the `/crops` page uses the middle crop as the representative card image, supports drag-and-drop query upload, and opens a closable investigation modal for detailed review
- the investigation payload now includes detected-face and aligned-face previews for qualifying person tracks, and image-search responses include the uploaded-image face debug preview that the web UI renders
- the `/crops` page hides retired mock-source history by default and exposes an `Include retired history` toggle
- embeddings are computed from crop images only
- face extraction is attempted once per qualifying person track through the separate `face-api` sidecar
- metadata and embeddings are currently persisted in SQLite inside `/data/vision.sqlite3`
- crop artifacts are stored under `/data/artifacts` and now use the artifact slice of the shared media budget, default `2 GB` when the total local media budget is `10 GB`

## Current Limitations

- MobileCLIP2 uses a deterministic 512-dimensional histogram fallback when the requested runtime weights are unavailable, so local Qdrant collections stay schema-compatible
- the Docker image now pre-caches the default `MobileCLIP2-S0` weights so the first semantic query does not also need to download them
- when local `.env` keeps `VISION_EMBEDDING_ENABLED=false`, text search falls back to track metadata ranking instead of true text-to-image similarity, while image search still remains face-first
- the first `vision` start after rebuilding the image is slower than the earlier scaffold because the full detector, embedder, and tracking dependencies are installed in-container
- the first semantic search after a fresh service start can still take longer because MobileCLIP is loaded on demand rather than at app bind time
- some current `GET /api/v1/vision/status` responses still omit `embedding.state` and `embedding.detail` even though the intended contract includes them, so clients should treat missing embedding fields as unknown
- the first `face-api` start compiles InspireFace from the vendored `third_party/InspireFace` submodule and may download the `Megatron` pack into `/runtime`, so the face stage can report `service-unreachable` or `service-not-ready` until that bootstrap completes
- clones that skipped submodule initialization must run `git submodule update --init --recursive` before rebuilding the `face-api` or `vision` images
- the job processes the current point in each looping relay, not a hard reset to the exact beginning of the source file
- VLM is skipped
- track metadata is still persisted in the local SQLite store even though object and face embeddings are also upserted into Qdrant
- ROI filtering is a future schema feature, not part of the current processing loop
- historical tracks from retired mock sources remain in the SQLite store until explicit cleanup or `VISION_PURGE_RETIRED_MOCK_HISTORY=true` is enabled
- the default runtime intentionally favors one mock source and one worker unless you raise `MOCK_VIDEO_MAX_SOURCES` or `VISION_SEGMENT_WORKER_COUNT`
- face calls can still time out under heavier load even though the sidecar is healthy
- the current face-alignment preview is generated from the same five-point face landmarks used around extraction, but the underlying InspireFace feature extraction still runs through the standard SDK call path

## Model Assets

- detector weight: `/app/yolov8n.pt`
- MobileCLIP cache: `/root/.cache/huggingface/hub/models--timm--MobileCLIP2-S0-OpenCLIP/.../open_clip_model.safetensors`
- keep local backups outside Git; see [docs/model-assets.md](../../docs/model-assets.md)
