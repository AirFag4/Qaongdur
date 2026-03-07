# vision

FastAPI scaffold for ingest orchestration, demo detection pipelines, recording helpers, and future AI enrichment stages.

## Local Setup

1. Copy `.env.example` to `.env`.
2. Run the service with `uv run qaongdur-vision`.

Container path:

```bash
cp .env.example .env
make vision-up
```

## Current Endpoints

- `GET /healthz`
- `GET /readyz`
- `GET /api/v1/vision/pipelines`
- `POST /api/v1/vision/demo/run`

This is intentionally a scaffold. The full detection-to-alert integration with `services/control-api` still belongs to the next backend implementation pass.
