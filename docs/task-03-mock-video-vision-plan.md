# Task 03 Mock Video Vision Plan

Planning document for the next Task 03 implementation slice.

## Goal

Use the local mock videos in `/Users/home/Desktop/AI_modelling_dev/AirFag4/Video` to build the first real vision-processing path for Qaongdur:

- detect only `person` and `vehicle`
- sample only `1-3` frames per second per camera
- track detections across frames
- save crop artifacts for the first frame, the middle frame, and the last frame before track loss
- compute embeddings from object crops only
- skip VLM for now
- gate face recognition so it only runs for person tracks that survive long enough, and only once per track
- persist crop and track metadata for a new crop-gallery page
- enforce a bounded local storage budget of `10 GB` for this test slice

## Current Constraints

The environment is not ready for every requested dependency to be fully real on day one:

- `services/vision` is currently only a demo scaffold
- the vendored `third_party/InspireFace` submodule contains Python wrappers, but the expected native runtime libraries still need a local compile step and model-pack hydration before the face stage can serve requests
- no local MobileCLIP2 repo or weights are vendored beside the workspace

Because of that, this implementation will prioritize:

- a real detector
- a real tracker
- real crop extraction and persisted metadata
- a real fixed-budget artifact store
- a real crop-gallery page
- pluggable embedding and face hooks, with runtime gating where assets are unavailable

## Delivery Scope

### 1. Vision pipeline

Implement a real `services/vision` pipeline for local mock videos.

Input:

- `people-walking.mp4`
- `vehicles.mp4`

Processing rules:

- decode local files with OpenCV
- sample frames at a configurable rate, default `2 fps`
- run a detector that keeps only `person`, `car`, `truck`, `bus`, and `motorcycle`
- normalize all vehicle classes into `vehicle`
- assign stable track ids with an internal IoU-based tracker
- close tracks after a short gap timeout

Track outputs:

- `first_seen_at`
- `middle_seen_at`
- `last_seen_at`
- `first`, `middle`, and `last` crop artifacts
- one object embedding per track, computed from the selected crop image only
- one optional face embedding per person track, only after the track survives the minimum dwell window and only once per track

### 2. Storage and quota

Implement a local artifact store under a dedicated vision data directory.

Initial storage behavior:

- store crop JPEGs for `first`, `middle`, and `last`
- store small metadata records for tracks, detections, and embedding status
- enforce a `10 GB` total budget for local artifacts
- prune oldest non-pinned artifacts before accepting new writes

This slice will treat the storage backend as quota-managed local disk storage. The future Postgres plus object-storage path remains the long-term design.

### 3. Metadata persistence

Implement a local relational metadata store for this slice, shaped so it can later move into Postgres with minimal contract churn.

Initial local tables:

- `video_source`
- `processing_job`
- `track`
- `storage_artifact`
- `track_embedding`
- `track_face_embedding`
- `storage_artifact`

For this implementation, SQLite is acceptable inside `services/vision` because:

- Task 03 currently has no database schema in place for vision data
- the current Postgres service does not yet expose `pgvector`
- the main value of this slice is the pipeline, crop persistence, and frontend contract

The schema will still be designed to migrate into Postgres later.

### 4. ROI-capable future schema design

Future ROI support should be designed now even if not implemented in the processing loop yet.

Future tables:

- `roi_zone`
- `roi_zone_vertex`
- `roi_rule`
- `roi_rule_label_filter`
- `track_roi_intersection`

Future behavior:

- operators define polygons in image coordinates for a specific camera
- rules decide whether a detection is counted only when a track intersects, enters, exits, or dwells in a zone
- track level events can later be filtered by ROI, label, direction, and dwell time

This design should avoid baking ROI geometry into detection records directly.

### 5. API surface

Expose the new data through `control-api`, not directly from the frontend to `vision`.

New or extended backend flows:

- `control-api` proxies vision job execution and crop-gallery reads
- shared TypeScript DTOs describe sources, jobs, track cards, and crop assets
- the web app continues using `@qaongdur/api-client`

Planned endpoints:

- `POST /api/v1/vision/mock-jobs/run`
- `GET /api/v1/vision/mock-sources`
- `GET /api/v1/vision/crop-tracks`
- `GET /api/v1/vision/crop-tracks/{trackId}`
- `GET /api/v1/vision/assets/{assetId}`
- `GET /api/v1/vision/storage`

### 6. Crop gallery page

Add a new page to the web console for track crops.

UI requirements:

- fixed card aspect ratio across the whole page
- one card per completed or active track
- show first, middle, and last crop states consistently
- show source camera, label, first seen time, last seen time, embedding status, and face status
- support source and label filtering
- keep the layout visually stable even when images have different original crop sizes

### 7. Model strategy for this slice

Detector:

- use a small open detector suitable for CPU demo work
- keep only person and vehicle classes in the stored output contract

Embedding:

- prefer the smallest official MobileCLIP2 variant available through OpenCLIP integration
- compute embeddings from object crops only
- if the runtime model is unavailable, keep the pipeline alive with a deterministic fallback embedder and surface the model status in metadata

Face:

- only evaluate person tracks
- only evaluate after a track lives past a dwell threshold
- only run once per track
- gate the stage behind a config flag and runtime availability check because local InspireFace runtime assets are not fully present yet

VLM:

- skipped in this slice

## Implementation Notes

### Processing mode

This slice should behave like a VMS-backed mock-camera flow.

That means:

- mock videos are the primary authoring source
- `mock-streamer` loops those files into MediaMTX as RTSP mock cameras
- `services/vision` consumes the MediaMTX relay URL rather than opening the file path directly
- each processing run is bounded to one source-duration window even though the publisher loops forever
- track association is handled by `supervision.ByteTrack` from the vendored `third_party/supervision` submodule
- the crop page is driven by stored outputs, not by websocket-only transient events

### Frame rate

Default sampling target:

- `2 fps`

Allowed config range:

- minimum `1 fps`
- maximum `3 fps`

### Vehicle class mapping

Persist only:

- `person`
- `vehicle`

Detector-native labels like `car`, `truck`, `bus`, and `motorcycle` are normalized to `vehicle` before persistence.

## Out Of Scope For This Pass

- VLM summarization
- production-grade re-identification search
- true Postgres plus `pgvector` rollout
- ROI drawing UI
- live RTSP vision inference
- full alert and incident generation from vision outputs
- moving InspireFace from runtime bootstrap to a prebuilt packaged runtime

## Expected Deliverables

- a planning doc before coding
- a real mock-video processing path in `services/vision`
- persisted crop and track metadata
- a `control-api` integration layer for that metadata
- a new crop-gallery page in the web app
- updated implementation docs after coding finishes

## Implementation Status

Completed in the current slice:

- local mock-video discovery from the sibling `Video/` directory
- system-managed mock cameras exposed through `control-api` from that same `Video/` directory
- looping RTSP publication of those files into MediaMTX with a stable `mock-video-*` path naming scheme
- detector contract narrowed to `person` and `vehicle`
- sampled processing constrained to `1-3 fps`, default `2 fps`
- packaged `supervision.ByteTrack` with closed-track first, middle, and last crop outputs
- crop-only embedding stage with runtime fallback when MobileCLIP2 weights are unavailable
- face stage gated to person tracks, minimum dwell time, and one embedding attempt per track
- separate `face-api` sidecar that bootstraps InspireFace from the vendored `third_party/InspireFace` submodule and targets the `Megatron` resource pack
- SQLite-backed metadata store for sources, jobs, tracks, crop assets, and embeddings
- quota-managed crop artifact storage with a `10 GB` default budget
- `control-api` proxy endpoints for sources, job execution, status, and crop-track reads

Current limitations after implementation:

- the first `face-api` startup compiles InspireFace from source and may download the `Megatron` pack into `/runtime`, so it can take several minutes before the face stage becomes reachable
- the first `vision` startup after an image rebuild is slower than the earlier scaffold because packaged detector, embedder, and tracker dependencies are now installed in the image
- clones that skipped `--recurse-submodules` must initialize `third_party/InspireFace` before the face image can build
- each job processes the current point in the looping RTSP source rather than resetting the publisher to the exact first frame
- `/crops` page with fixed-aspect track cards, representative middle-crop imagery, and runtime status
- Compose wiring for `vision-cpu` with persistent `vision-data`
- local recording-pruner sidecar for the MediaMTX recordings volume with a `10 GB` default budget

Current implementation gaps relative to the long-term design:

- embeddings are stored in SQLite tables, not a true vector-search index yet
- ROI filtering is still design-only
- the first `face-api` startup is expensive because it compiles InspireFace from source and may download the `Megatron` pack at runtime instead of consuming a prebuilt packaged runtime
- the current face path still depends on the `third_party/InspireFace` submodule being initialized before the image can build
- VLM remains intentionally skipped
