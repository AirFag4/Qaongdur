# Codex Prompt: Vision Investigation, Identity Search, Map, and ROI

You are Codex extending Qaongdur from a basic recorded-chunk crop gallery into a real investigation surface for operators. This prompt should turn the current crop, face, embedding, and camera metadata slices into a usable investigation workflow before any serious agent-chat work starts.

## Primary Goal

Build the next product milestone around:

- track-detail investigation UX
- full-frame review with bbox overlays
- camera geolocation and map view
- face identity and watchlist workflows
- crop search by text and image
- persisted ROI drawing with CVAT-like polygon interaction

Agent chat stays downstream of this work.

## Execution Order

Run this prompt after:

1. `docs/codex-prompts/03-backend-vms-ai-platform.md`
2. the `core` runtime slice of `docs/codex-prompts/05-docker-open-source-platform.md`

Run this prompt before:

1. `docs/codex-prompts/04-agent-chat-openclaw.md`

Treat this prompt as the next major feature wave. It can be extended later, but do not skip ahead to agent chat until the data model, search surfaces, and investigation UI here are stable.

## Product Direction

The current crop page is only a first inspection surface. Replace that narrow flow with a broader investigation model:

1. operator reviews tracked detections
2. operator opens a large closable investigation card or modal
3. operator sees the original source frame with stored bbox overlays
4. operator pivots into related tracks, related faces, text search, or map context
5. operator draws or edits ROIs on the camera frame
6. later, the agent can use these stable surfaces as tools

## Workstream A: Track Investigation UX

Replace the current side-detail-only crop view with a larger review surface.

Required behavior:

- clicking a crop card opens a closable modal, drawer, or large detail card
- the detail view shows the source frame that matches the stored observation timestamp, not just the cropped object
- draw the stored bbox on that source frame
- support toggling between `start`, `middle`, and `end` observations for the track
- each drawn bbox must show the observation timestamp above or attached to the box
- preserve and show the saved track movement points for start, middle, and end
- keep direct links to the source camera and playback time window

Important correctness rule:

- default to exact captured frame review rather than current live stream when showing stored bbox overlays, because a historical bbox drawn on a current live frame is misleading
- if desired, add a separate `Open Live` action for the source camera, but do not treat that live view as the canonical bbox-review surface

## Workstream B: Camera Geolocation And Device Map

Extend camera and device metadata with geospatial coordinates.

Required data:

- `latitude`
- `longitude`
- optional `heading`
- optional human-readable location note

Required UX:

- show camera coordinates on the device detail surface
- add a device-map page or device-map mode that renders all geolocated cameras
- clicking a map marker should open the camera/device detail and link to live, playback, and crops

Implementation direction:

- use one open-source map stack only
- prefer `MapLibre GL JS` with open map tiles unless the existing repo direction changes
- keep map dependencies lightweight and self-hostable

## Workstream C: Face Detection, Identity, And Lists

The current face flow is too narrow. Expand it into an identity workflow.

Required behavior:

- attempt face detection for all stored person-track observations, not only dwell-gated tracks
- start with the saved `start`, `middle`, and `end` source frames for each person track
- keep track-level face status visible in the UI and API
- if multiple faces are found in one person observation, record that explicitly instead of hiding it

Add identity-list support:

- whitelist
- blacklist
- user-defined named lists

Required entities:

- `identity_subject`
- `identity_alias`
- `identity_list`
- `identity_list_membership`
- `identity_reference_face`
- `face_match_event`
- `face_review_decision`

Behavior requirements:

- watchlists must support multiple list memberships per subject
- matches must stay reviewable and auditable
- false positives must be dismissible without deleting the underlying track
- identity workflows must support manual confirmation and rejection

## Workstream D: Search By Text, Face Image, And Embedding

The current crop search is metadata-only. Expand it into multimodal search.

Use one vector database only:

- keep `Qdrant` as the repo-standard vector database for both MobileCLIP object embeddings and face embeddings
- do not introduce a second vector database for this milestone

Required search modes:

- time and camera filtering
- label filtering
- text-to-crop search using MobileCLIP text embeddings
- uploaded face-image search using face detection plus face embedding
- later extension path for uploaded object-image search

Text search requirements:

- search crop tracks by natural language over stored MobileCLIP vectors
- allow hybrid filters: `camera + time + label + text`
- return scores plus enough context for operator review

Face-image search requirements:

- user uploads an image
- system runs face detection on the uploaded image first
- system embeds the best candidate face or selected face region
- system searches against stored face vectors
- results must open into the same investigation detail flow

## Workstream E: ROI Authoring And Filtering

Persisted ROI support is no longer optional. Build it as a first-class operator tool.

Required capabilities:

- fetch a target camera frame for annotation
- draw polygon ROIs on that frame
- store multiple ROIs per camera
- name, color, enable, disable, and delete ROIs
- filter detections and tracks by ROI intersection
- keep ROI editing separate from track review, but cross-link them

Interaction requirement:

- the polygon authoring feel must intentionally match `CVAT` polygon annotation behavior as closely as possible
- this includes open-polygon tinting, active point feedback, cursor-follow preview, and clear close-polygon affordances
- prefer reusing CVAT polygon interaction logic or adapting its annotation tooling instead of inventing a simplified generic canvas editor

Do not ship a loose approximation if the interaction feels substantially worse than CVAT.

## Data Model Direction

Move the current schema toward a more investigation-friendly layout.

Add or plan for:

- `camera.latitude`
- `camera.longitude`
- `camera.heading`
- `track_observation`
- `track_frame`
- `track_bbox`
- `track_face_candidate`
- `roi_zone`
- `roi_zone_vertex`
- `track_roi_intersection`
- `identity_subject`
- `identity_list`
- `identity_reference_face`
- `vector_embedding`

Important storage rule:

- keep source-frame references and bbox coordinates separately from derived crop artifacts
- treat source-frame review as the primary evidence surface
- treat crops as derived shortcuts

## API Requirements

Extend `control-api` and `vision` so the frontend can use stable typed endpoints for:

- track-detail fetch with source-frame overlays
- track observations for `start`, `middle`, and `end`
- camera geolocation CRUD
- device-map query
- ROI CRUD
- ROI intersection filtering
- text search over crop embeddings
- face-image search
- identity-list CRUD
- face-match review actions

Keep shared DTOs in `packages/types`.

## Frontend Requirements

Add or extend pages and components for:

- crop investigation modal or large closable detail card
- source-frame bbox overlay viewer
- device map
- ROI authoring surface
- face-list management
- text search and face-image search controls

Preserve the operator-console visual language already in the repo.

## Runtime And Performance Requirements

Do not assume high-end hardware.

For this milestone:

- keep chunk-driven analytics as the primary backend flow
- keep camera count and worker count tunable from runtime settings
- avoid re-embedding unchanged artifacts unnecessarily
- add backfill and reindex paths for new search modes
- allow face processing to run as a sidecar if `services/vision` should stay lighter

## Deliverables

- upgraded track investigation UX with source-frame overlays
- camera geolocation support and device map
- expanded face pipeline for all person-track observations
- identity-list and watchlist backend models
- text-to-crop search
- uploaded face-image search
- persisted ROI polygons with CVAT-like interaction expectations documented in code and docs
- updated docs and API contracts

## Acceptance Criteria

- clicking a crop track opens a closable investigation surface with source-frame bbox overlays for `start`, `middle`, and `end`
- camera coordinates are stored and visible on a device map
- face detection is attempted for every stored person track observation set, with explicit status in the API
- whitelist, blacklist, and named user lists exist and can be attached to subjects
- text search returns crop-track results from MobileCLIP embeddings
- uploaded face-image search returns track or subject matches from face embeddings
- ROIs can be drawn, saved, edited, and used to filter track results
- the ROI drawing interaction is intentionally aligned with CVAT polygon editing rather than a generic placeholder tool
- this milestone is considered the required foundation before serious agent-chat work begins
