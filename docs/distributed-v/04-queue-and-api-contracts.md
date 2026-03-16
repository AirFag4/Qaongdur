# Queue And API Contracts

## Queue Stack

Use `Celery` workers with `Redis` as the broker.

This gives:

- pull-based load balancing
- simple worker scaling across hosts
- queue routing by capability
- low implementation cost relative to the current codebase

## Queue Names

Start with explicit queues instead of fully dynamic routing:

- `vision.cpu`
- `vision.cpu.face`
- `vision.gpu`
- `vision.gpu.face`
- `vision.backfill`
- `vision.maintenance`

Workers subscribe only to the queues they can satisfy.

## Task Types

Phase 1 task set:

- `vision.process_segment`
- `vision.retry_face`
- `vision.backfill_embeddings`
- `vision.reindex_vectors`

Do not add live-stream lease tasks in phase 1. Keep the first distributed version segment-based.

## Primary Task Payload

### `vision.process_segment`

```json
{
  "jobId": "0f4a58d7-7e61-42c5-a0f9-7fe98d0f95d2",
  "jobType": "process-segment",
  "segmentId": "0f7e2b9e-7bf4-4d9f-b9d2-8f2a10ca6b32",
  "sourceId": "source-local-01",
  "siteId": "site-local-01",
  "cameraId": "cam-local-01",
  "cameraName": "Front Gate",
  "segment": {
    "bucket": "qaongdur-dev",
    "objectKey": "recordings/site-local-01/cam-local-01/2026/03/16/0f7e2b9e.mp4",
    "sha256": "abc123...",
    "segmentStartAt": "2026-03-16T12:00:00Z",
    "durationSec": 60.0
  },
  "pipeline": {
    "sampleFps": 2.0,
    "detectorModel": "yolo26n",
    "embeddingEnabled": true,
    "embeddingModel": "MobileCLIP2-S0",
    "faceEnabled": true,
    "faceModel": "Megatron"
  },
  "requiredCapabilities": {
    "supportsTextEmbedding": true,
    "supportsImageEmbedding": true,
    "supportsFace": true,
    "supportsGpu": false
  },
  "attemptNo": 1,
  "requestedAt": "2026-03-16T12:01:00Z"
}
```

## Secondary Task Payloads

### `vision.retry_face`

Use when the segment was processed but face extraction failed for recoverable reasons.

```json
{
  "jobId": "c2f3c980-c2c3-4d82-9e7a-80e338ea4c74",
  "jobType": "retry-face",
  "trackIds": [
    "track-1",
    "track-2"
  ],
  "requiredCapabilities": {
    "supportsFace": true
  },
  "attemptNo": 2
}
```

### `vision.backfill_embeddings`

Use when vectors were skipped because the embedder or Qdrant was degraded.

```json
{
  "jobId": "8a3f6d75-f5af-4ce9-a478-3ac8f5a2d178",
  "jobType": "backfill-embeddings",
  "observationIds": [
    "obs-1",
    "obs-2"
  ],
  "embeddingKind": "object",
  "requiredCapabilities": {
    "supportsImageEmbedding": true
  },
  "attemptNo": 1
}
```

## Worker Registration Contract

`vision-worker` should register over HTTP at startup.

### `POST /api/v1/internal/analytics/workers/register`

```json
{
  "workerId": "5f8461dc-1dcc-40ef-8a98-4cb0ca8ae041",
  "node": {
    "name": "ati-local-home",
    "sshAlias": "ati-local-home",
    "hostname": "ati-local-home.local",
    "gpuAvailable": false,
    "gpuName": null,
    "dockerVersion": "28.0.4",
    "nvidiaRuntimeVersion": null
  },
  "worker": {
    "workerName": "vision-worker-1",
    "queueNames": [
      "vision.cpu",
      "vision.cpu.face"
    ],
    "capacitySlots": 1,
    "supportsFace": true,
    "supportsTextEmbedding": true,
    "supportsImageEmbedding": true,
    "supportsGpu": false,
    "detectorModel": "yolo26n",
    "embeddingModel": "MobileCLIP2-S0",
    "faceModel": "Megatron"
  }
}
```

## Worker Heartbeat Contract

### `POST /api/v1/internal/analytics/workers/heartbeat`

```json
{
  "workerId": "5f8461dc-1dcc-40ef-8a98-4cb0ca8ae041",
  "status": "healthy",
  "activeJobs": 1,
  "queueDepthHint": 0,
  "runtime": {
    "cpuPercent": 82.1,
    "memoryPercent": 64.3,
    "gpuPercent": null,
    "gpuMemoryPercent": null
  },
  "checkedAt": "2026-03-16T12:02:15Z"
}
```

## Job Status Updates

Workers should write job state transitions through one internal API.

### `POST /api/v1/internal/vision/jobs/{jobId}/status`

Allowed statuses:

- `running`
- `completed`
- `retryable-failed`
- `failed`

Suggested payload:

```json
{
  "workerId": "5f8461dc-1dcc-40ef-8a98-4cb0ca8ae041",
  "attemptNo": 1,
  "status": "completed",
  "detail": "Processed 2 tracks and 14 observations.",
  "metrics": {
    "framesDecoded": 120,
    "framesSampled": 14,
    "tracksClosed": 2,
    "observationsWritten": 14,
    "faceObservationsWritten": 3,
    "durationMs": 18420
  }
}
```

## Idempotency Rules

- `recording-sync` must be able to submit the same segment more than once without creating duplicate jobs.
- `vision.process_segment` must be safe to retry for the same `jobId` and `attemptNo`.
- `track_observation` writes should use deterministic IDs derived from `track_id + frame_index` if practical.
- artifact object keys should be deterministic so retries overwrite the same logical artifact instead of leaking blobs.
- Qdrant point IDs should include the observation or face-observation ID so repeated upserts replace rather than duplicate.

## Failure Rules

- decode or model errors that are likely host-specific should become `retryable-failed`
- schema or payload validation errors should become terminal `failed`
- worker heartbeat timeout should move the worker to `offline`
- jobs assigned to an offline worker should be released after a lease timeout and retried

## Read API Contracts For The UI

### `GET /api/v1/vision/tracks/{trackId}/observations`

Return:

- track summary
- ordered observation list
- bbox per sampled frame
- object embedding reference per observation when available
- nested face observations when available

### `GET /api/v1/vision/observations/{observationId}`

Return:

- one observation
- crop artifact URL
- frame overlay URL
- face detections
- aligned face image URLs

## Search Query Contract

Keep the current multimodal search shape, but extend results with frame-level anchors:

- `matchedObservationId`
- `matchedCapturedAt`
- `matchedFaceObservationId`

That lets the UI land directly on the exact frame that produced the top hit.
