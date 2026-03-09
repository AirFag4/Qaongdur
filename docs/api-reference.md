# Qaongdur API Reference

Developer reference for the current Qaongdur data contract, the web app integration points, and the planned backend API shape.

## Scope

This document covers three layers:

1. The API contract that exists today in TypeScript.
2. The way `apps/web` consumes that contract.
3. The recommended HTTP/WebSocket shape for the future backend services.

## Status Legend

- `Implemented`: exists in the repo today and is used by the web app.
- `Partial`: a scaffold exists in the repo, but the full surface is not implemented yet.
- `Planned`: called out in product and architecture docs, but not implemented yet.
- `Recommended`: inferred backend shape to keep the frontend contract stable when mocks are replaced.

## Boundary Map

| Layer | Path | Responsibility | Status |
| --- | --- | --- | --- |
| Shared DTOs | `packages/types/src/index.ts` | Source of truth for entities, filters, realtime events, and the `VmsApiClient` interface | Implemented |
| API adapter | `packages/api-client/src/index.ts` | Creates the API client and realtime socket used by the frontend | Implemented |
| Mock data source | `packages/api-client/src/mock-api-client.ts` | Mock implementation of `VmsApiClient` | Implemented |
| Mock realtime transport | `packages/api-client/src/mock-event-socket.ts` | Mock websocket-like event feed | Implemented |
| Frontend API bootstrap | `apps/web/src/lib/api.ts` | Instantiates the client/socket and defines React Query keys | Implemented |
| Control plane backend | `services/control-api` | FastAPI service with Keycloak token validation, camera onboarding, live/playback/device endpoints, auth endpoints, approval examples, and audit logging hooks | Partial |
| Vision pipeline | `services/vision` | Mock-video vision pipeline with tracked crop persistence, embeddings, and runtime status endpoints | Partial |
| Agent backend | `services/agent` | In-app assistant sessions, tool calls, approvals, audit trails | Planned |

## Current TypeScript API Surface

### Client factory

Current package exports:

- `createApiClient(config?): VmsApiClient`
- `createRealtimeSocket(config?): RealtimeEventSocket`

Current behavior:

- `createApiClient()` returns the singleton `mockApiClient` when no backend config is provided.
- when `baseUrl` and `getAccessToken` are provided, the client uses the real HTTP backend for camera inventory, live tiles, overview, playback search, devices, and camera mutations, and only falls back to mocks on network failure for read-only queries.
- `createRealtimeSocket()` returns a `MockRealtimeEventSocket` only when no backend config is provided.
- when a real backend is configured, `createRealtimeSocket()` currently returns a disabled transport instead of fake events because backend event streaming is not wired yet.
- when a real backend is configured, `createCamera()`, `reconnectCamera()`, and `deleteCamera()` do not fall back to the mock adapter.

Current run modes:

- UI-only mock mode: start `pnpm --filter @qaongdur/web dev`
- hybrid auth mode: start Keycloak and `services/control-api`, then run the web app locally
- core container mode: run `make docker-up`, which starts the full local stack and uses the real backend for camera, live, overview, playback, and device routes
- VMS-backed mock-video mode: run `make vision-up`, which adds `mock-streamer`, `face-api`, and `vision` on top of the core stack so the crop pipeline consumes MediaMTX relay URLs instead of file paths

### `VmsApiClient`

The frontend only talks to the data layer through this interface:

| Method | Params | Returns | Current behavior | Web usage |
| --- | --- | --- | --- | --- |
| `listSites()` | none | `Promise<Site[]>` | returns all sites | layout bootstrapping |
| `listCameras(siteId?)` | optional `siteId` | `Promise<Camera[]>` | returns all cameras or a site-scoped subset | layout bootstrapping, site switcher |
| `createCamera(input)` | `CreateCameraInput` | `Promise<Camera>` | creates a persisted RTSP camera through the backend | devices page |
| `reconnectCamera(cameraId)` | camera id | `Promise<Camera>` | rebuilds the MediaMTX path for an existing camera | devices page |
| `deleteCamera(cameraId)` | camera id | `Promise<void>` | removes the camera from backend storage and MediaMTX | devices page |
| `listLiveTiles(siteId?)` | optional `siteId` | `Promise<LiveStreamTile[]>` | returns live stream state and detections | live page |
| `getOverview(siteId?)` | optional `siteId` | `Promise<OverviewSnapshot>` | computes summary metrics, incidents, alerts, and health buckets | overview page |
| `listAlerts(filter?)` | `AlertFilter` | `Promise<AlertEvent[]>` | supports site, camera, severity, status, and text filtering | alerts page, live side rail |
| `listIncidents()` | none | `Promise<Incident[]>` | returns all incidents | incident page list |
| `getIncidentById(id)` | incident id | `Promise<Incident \| undefined>` | finds one incident in mock storage | incident detail page |
| `searchPlayback(params)` | `PlaybackSearchParams` | `Promise<PlaybackSegment[]>` | returns MediaMTX recording spans with browser playback and downloadable MP4 URLs in backend mode and generated 15-minute buckets in mock mode | playback page |
| `listDevices(siteId?)` | optional `siteId` | `Promise<Device[]>` | returns all devices or a site-scoped subset | devices page |
| `listVisionSources()` | none | `Promise<VisionSource[]>` | returns camera-oriented vision sources with MediaMTX relay URLs and processed-segment counts | crop gallery page |
| `getVisionStatus()` | none | `Promise<VisionPipelineStatus>` | returns detector, embedding, face-sidecar, vector-store, queue, and storage status | crop gallery page |
| `runVisionMockJob(sourceIds?)` | optional source ids | `Promise<VisionJobStatus>` | requests an immediate recordings scan in backend mode | crop gallery page |
| `listCropTracks(filter?)` | `CropTrackFilter` | `Promise<CropTrack[]>` | returns stored first, middle, and last crop states per track with time-range filtering and optional retired-history inclusion | crop gallery page |
| `getCropTrack(trackId)` | track id | `Promise<CropTrackDetail \| undefined>` | returns detailed movement, bbox, and timing info for one track | crop gallery page |
| `getSystemSettings()` | none | `Promise<SystemSettings>` | returns the current auth and env-backed runtime settings surface used by the Settings page | settings page |

### `RealtimeEventSocket`

The current realtime abstraction is intentionally small:

| Method | Purpose | Status |
| --- | --- | --- |
| `connect()` | starts the transport | Implemented |
| `disconnect()` | stops the transport | Implemented |
| `subscribe(handler)` | registers a listener and returns an unsubscribe function | Implemented |

Current mock behavior:

- emits one event every 8 seconds
- emits `alert.created` about 65% of the time
- emits `camera.health_changed` otherwise
- does not require auth, acknowledgements, or reconnection logic yet

Current backend behavior:

- the UI still renders the realtime rail
- fake events are disabled when the web app is pointed at the real backend
- the rail shows that backend realtime streaming is not wired yet instead of mixing fake data into a real session

## Shared Domain Models

All of the following types live in `packages/types/src/index.ts`.

### Enums and string unions

| Type | Allowed values |
| --- | --- |
| `HealthStatus` | `healthy`, `warning`, `critical`, `offline` |
| `AlertSeverity` | `low`, `medium`, `high`, `critical` |
| `IncidentStatus` | `open`, `triaging`, `investigating`, `resolved` |
| `AlertStatus` | `new`, `acknowledged`, `investigating`, `resolved` |
| `DeviceType` | `camera`, `nvr`, `gateway`, `sensor` |
| `RtspTransport` | `automatic`, `udp`, `multicast`, `tcp` |

### `Site`

- `id: string`
- `name: string`
- `code: string`
- `region: string`

### `Camera`

- `id: string`
- `siteId: string`
- `name: string`
- `zone: string`
- `streamUrl: string`
- `liveStreamUrl?: string | null`
- `playbackPath?: string | null`
- `rtspTransport?: RtspTransport`
- `rtspAnyPort?: boolean`
- `health: HealthStatus`
- `fps: number`
- `resolution: string`
- `uptimePct: number`
- `lastSeenAt: string`
- `tags: string[]`

### `DetectionBox`

- `id: string`
- `label: string`
- `confidence: number`
- `severity: AlertSeverity`
- `x: number`
- `y: number`
- `width: number`
- `height: number`

### `LiveStreamTile`

- `cameraId: string`
- `isLive: boolean`
- `latencyMs: number`
- `bitrateKbps: number`
- `detections: DetectionBox[]`
- `hlsUrl?: string | null`

### `AlertEvent`

- `id: string`
- `cameraId: string`
- `siteId: string`
- `title: string`
- `summary: string`
- `rule: string`
- `severity: AlertSeverity`
- `status: AlertStatus`
- `confidence: number`
- `happenedAt: string`

### `EvidenceClip`

- `id: string`
- `cameraId: string`
- `title: string`
- `type: "video" | "snapshot" | "report"`
- `startAt: string`
- `endAt: string`
- `durationSec: number`
- `storageRef: string`

### `IncidentTimelineItem`

- `id: string`
- `happenedAt: string`
- `actor: string`
- `action: string`
- `note: string`

### `Incident`

- `id: string`
- `title: string`
- `siteId: string`
- `severity: AlertSeverity`
- `status: IncidentStatus`
- `openedAt: string`
- `closedAt?: string`
- `cameraIds: string[]`
- `owner: string`
- `summary: string`
- `tags: string[]`
- `timeline: IncidentTimelineItem[]`
- `evidence: EvidenceClip[]`

### `PlaybackSegment`

- `id: string`
- `cameraId: string`
- `startAt: string`
- `endAt: string`
- `alerts: number`
- `motionScore: number`
- `durationSec?: number`
- `playbackUrl?: string`
- `downloadUrl?: string`

### `Device`

- `id: string`
- `cameraId?: string`
- `siteId: string`
- `name: string`
- `type: DeviceType`
- `model: string`
- `ipAddress: string`
- `firmware: string`
- `health: HealthStatus`
- `lastHeartbeatAt: string`
- `uptimePct: number`
- `packetLossPct: number`

### `OverviewMetric`

- `label: string`
- `value: string`
- `delta: string`
- `trend: "up" | "down" | "flat"`

### `OverviewSnapshot`

- `metrics: OverviewMetric[]`
- `topAlerts: AlertEvent[]`
- `activeIncidents: Incident[]`
- `streamHealth: { label: string; value: number }[]`

### `AlertFilter`

- `siteId?: string`
- `cameraId?: string`
- `severity?: AlertSeverity | "all"`
- `status?: AlertStatus | "all"`
- `search?: string`

### `CreateCameraInput`

- `siteId?: string`
- `name: string`
- `zone: string`
- `rtspUrl: string`
- `rtspTransport?: RtspTransport`
- `rtspAnyPort?: boolean`

### `PlaybackSearchParams`

- `cameraIds: string[]`
- `from: string`
- `to: string`
- `includeAlerts: boolean`

### `VisionSource`

- `id: string`
- `siteId: string`
- `cameraId: string`
- `cameraName: string`
- `pathName: string`
- `relayRtspUrl: string`
- `liveStreamUrl?: string | null`
- `sourceKind: string`
- `ingestMode: string`
- `health: HealthStatus`
- `trackCount: number`
- `processedSegmentCount: number`
- `latestProcessedAt?: string | null`
- `lastSegmentAt?: string | null`
- `retiredAt?: string | null`

### `VisionPipelineStatus`

- `sampleMode: boolean`
- `autoIngest?: boolean`
- `detector: { available: boolean; modelName: string; detail: string }`
- `embedding: { modelName: string }`
- `face: { available: boolean; enabled: boolean; mode: string; modelName: string; detail: string }`
- `vectorStore?: { enabled: boolean; available: boolean; provider: string; detail: string }`
- `sourceSync?: { lastSyncedAt?: string | null; error?: string | null }`
- `queueDepth?: number`
- `segmentWorkerCount?: number`
- `sampleFps?: number`
- `latestJob?: VisionJobStatus | null`
- `storage: VisionStorageStatus`

### `VisionJobStatus`

- `id: string`
- `status: "running" | "completed" | "failed"`
- `sourceIds: string[]`
- `sampledFps: number`
- `trackCount: number`
- `startedAt: string`
- `finishedAt?: string | null`
- `detail?: string | null`

### `CropTrackFilter`

- `sourceId?: string`
- `cameraId?: string`
- `label?: "person" | "vehicle" | "all"`
- `fromAt?: string`
- `toAt?: string`
- `includeRetired?: boolean`

### `CropTrack`

- `id: string`
- `sourceId: string`
- `siteId: string`
- `cameraId: string`
- `cameraName: string`
- `label: "person" | "vehicle"`
- `detectorLabel: string`
- `firstSeenAt: string`
- `middleSeenAt: string`
- `lastSeenAt: string`
- `firstSeenOffsetMs: number`
- `middleSeenOffsetMs: number`
- `lastSeenOffsetMs: number`
- `firstSeenOffsetLabel: string`
- `middleSeenOffsetLabel: string`
- `lastSeenOffsetLabel: string`
- `frameCount: number`
- `sampleFps: number`
- `maxConfidence: number`
- `avgConfidence: number`
- `embeddingStatus: string`
- `embeddingModel?: string | null`
- `faceStatus: string`
- `faceModel?: string | null`
- `closedReason: string`
- `firstCropDataUrl: string`
- `middleCropDataUrl: string`
- `lastCropDataUrl: string`

### Realtime event types

`RealtimeEvent` is a union of:

- `RealtimeAlertEvent`
  - `type: "alert.created"`
  - `payload: AlertEvent`
- `RealtimeHealthEvent`
  - `type: "camera.health_changed"`
  - `payload: { cameraId: string; health: HealthStatus; happenedAt: string }`

## Web App Contract

The frontend route layer is already stable and should be treated as the first consumer contract.

### Routes and API calls

| Route | Page | Calls | Notes |
| --- | --- | --- | --- |
| `/` | Overview | `getOverview(siteId)` | site-scoped dashboard snapshot |
| `/live` | Live monitoring | `listLiveTiles(siteId)`, `listAlerts({ siteId, status: "new" })` | right rail shows new alerts only |
| `/alerts` | Alerts and events | `listAlerts({ siteId, severity, status, search })` | filters are client-owned form state |
| `/incidents` | Incident detail | `listIncidents()` then `getIncidentById(id)` | redirects to first incident if no id is present |
| `/incidents/:incidentId` | Incident detail | `listIncidents()`, `getIncidentById(id)` | detail page |
| `/playback` | Playback search | `searchPlayback(params)` | query runs only after form submit |
| `/devices` | Devices | `listDevices(siteId)`, `createCamera(input)`, `reconnectCamera(cameraId)`, `deleteCamera(cameraId)` | search and type filter are local UI filters; reconnect and remove are admin-only |

### Layout bootstrapping

`OperatorLayout` loads:

- `listSites()`
- `listCameras(siteId)`

It also owns:

- selected site state
- selected camera ids
- live grid size
- recent realtime events
- command palette open state

### React Query keys

Current query key factory in `apps/web/src/lib/api.ts`:

| Key factory | Result |
| --- | --- |
| `queryKeys.sites` | `["sites"]` |
| `queryKeys.cameras(siteId)` | `["cameras", siteId ?? "all"]` |
| `queryKeys.liveTiles(siteId)` | `["live-tiles", siteId ?? "all"]` |
| `queryKeys.overview(siteId)` | `["overview", siteId ?? "all"]` |
| `queryKeys.alerts(filters)` | `["alerts", JSON.stringify(filters ?? {})]` |
| `queryKeys.incidents` | `["incidents"]` |
| `queryKeys.incident(id)` | `["incident", id]` |
| `queryKeys.playback(hash)` | `["playback", hash]` |
| `queryKeys.devices(siteId)` | `["devices", siteId ?? "all"]` |

Recommendation:

- keep these keys stable when swapping in a real backend
- if pagination is introduced later, include page cursors in the query key

## Current Mock Data Semantics

This is useful when replacing the mock layer with a real backend, because the web UI already assumes these behaviors.

### Inventory shape

- `3` sites
- `12` cameras per site
- `48` alerts total
- `4` incidents total
- `42` devices total

### Mock latency

Every `VmsApiClient` method waits for a random delay between roughly `140ms` and `360ms`.

### `getOverview(siteId?)`

Current computed behavior:

- scopes cameras by `siteId` when present
- derives `liveCount` from `LiveStreamTile.isLive`
- derives `warningCount` from cameras in `warning` or `critical` state
- derives `criticalAlerts` from scoped alerts
- returns the first `8` alerts as `topAlerts`
- returns the first `4` scoped incidents as `activeIncidents`
- does not currently filter `activeIncidents` by `status !== "resolved"`

Backend implication:

- the real backend should return already-computed overview data instead of forcing the web app to aggregate it client-side

### `listAlerts(filter?)`

Current filter behavior:

- exact-match filters for `siteId`, `cameraId`, `severity`, and `status`
- `severity: "all"` and `status: "all"` are treated as no filter
- `search` matches lowercase text against `title`, `summary`, and `rule`

Backend implication:

- the real API should keep the same semantics to avoid frontend behavior drift

### `searchPlayback(params)`

Current generated behavior:

- uses `params.from` and `params.to`
- defaults to the first `6` cameras when `cameraIds` is empty
- generates `15` minute buckets
- returns between `4` and `40` segments
- always returns `alerts` and `motionScore`
- currently does not change behavior based on `includeAlerts`

Backend implication:

- `includeAlerts` is already part of the public contract and should stay in the request model even if the first backend version ignores it

## Recommended Control API HTTP Reference

This section mixes `Partial` and `Recommended` pieces. The auth scaffold exists in the repo today, while the main domain APIs below remain the recommended target surface for replacing frontend mocks.

### Base path

Recommended base path:

- `/api/v1`

### Authentication

Auth model:

- bearer token from the Keycloak browser session
- session reuse for both web data calls and agent calls

Current state:

- `services/control-api` validates Keycloak-issued bearer tokens through OIDC discovery and JWKS
- implemented auth endpoints include `GET /api/v1/auth/me` and `GET /api/v1/auth/allowed-actions`
- implemented approval examples include `POST /api/v1/agent/actions/evidence-export` and `POST /api/v1/agent/actions/purge-evidence`
- implemented domain endpoints now cover sites, cameras, live tiles, overview, playback search, and devices
- alerts and incidents currently return placeholder backend responses rather than a full detection-to-incident workflow

### REST endpoints

Current implemented and recommended next domain endpoints:

| Method | Path | Request | Response | Maps to |
| --- | --- | --- | --- | --- |
| `GET` | `/api/v1/sites` | none | `Site[]` | `listSites()` |
| `GET` | `/api/v1/cameras` | query: `siteId?` | `Camera[]` | `listCameras(siteId?)` |
| `POST` | `/api/v1/cameras` | body: `CreateCameraInput` | `Camera` | `createCamera(input)` |
| `POST` | `/api/v1/cameras/:cameraId/reconnect` | path param | `Camera` | `reconnectCamera(cameraId)` |
| `DELETE` | `/api/v1/cameras/:cameraId` | path param | `{ deleted, cameraId, name }` | `deleteCamera(cameraId)` |
| `GET` | `/api/v1/live-tiles` | query: `siteId?` | `LiveStreamTile[]` | `listLiveTiles(siteId?)` |
| `GET` | `/api/v1/overview` | query: `siteId?` | `OverviewSnapshot` | `getOverview(siteId?)` |
| `GET` | `/api/v1/alerts` | query: `siteId?`, `cameraId?`, `severity?`, `status?`, `search?` | `AlertEvent[]` | `listAlerts(filter?)` |
| `GET` | `/api/v1/incidents` | none | `Incident[]` | `listIncidents()` |
| `GET` | `/api/v1/incidents/:incidentId` | path param | `Incident` | `getIncidentById(id)` |
| `POST` | `/api/v1/playback/search` | body: `PlaybackSearchParams` | `PlaybackSegment[]` | `searchPlayback(params)` |
| `GET` | `/api/v1/devices` | query: `siteId?` | `Device[]` | `listDevices(siteId?)` |

Notes:

- use `POST` for playback search because the request already has a structured body and may grow later
- return `404` for a missing incident on `GET /api/v1/incidents/:incidentId`
- because `VmsApiClient.getIncidentById()` currently returns `Promise<Incident | undefined>`, the HTTP adapter should translate a `404` into `undefined` unless the frontend contract is changed
- keep response field names identical to the shared TypeScript interfaces

### Realtime endpoint

Recommended transport:

- `GET /api/v1/events/ws` as a WebSocket endpoint

Recommended query params:

- `siteId?`
- `cameraId?`

Recommended event payload:

```json
{
  "type": "alert.created",
  "payload": {
    "id": "alt-0042",
    "cameraId": "cam-hcm-01-01",
    "siteId": "site-hcm-01",
    "title": "Perimeter breach",
    "summary": "Movement pattern exceeded configured dwell threshold.",
    "rule": "rule-4",
    "severity": "critical",
    "status": "new",
    "confidence": 0.93,
    "happenedAt": "2026-03-07T05:12:00.000Z"
  }
}
```

Recommendation:

- emit exactly the same `RealtimeEvent` union used by the frontend today
- add ping or heartbeat messages only if they are wrapped in a backward-compatible envelope

### Health endpoints

This is not defined in `@qaongdur/types` yet, but the backend prompt expects service observability.

Recommended minimum endpoints:

- `GET /healthz`
- `GET /readyz`

Current state:

- `GET /healthz` is implemented in `services/control-api`
- `GET /readyz` is implemented in `services/control-api`

Recommended response:

```json
{
  "status": "ok",
  "service": "control-api",
  "version": "0.1.0"
}
```

## Recommended Agent API Reference

This section is `Recommended`, based on the agent planning brief and the placeholder UI in `apps/web/src/components/agent-chat-rail.tsx`.

Current state:

- the web app has no live agent API calls yet
- the right rail is a reserved shell plus a realtime event feed

Recommended base path:

- `/api/v1/agent`

Recommended endpoints:

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/api/v1/agent/sessions` | create a chat session for the current operator |
| `GET` | `/api/v1/agent/sessions/:sessionId` | fetch session metadata and message history |
| `POST` | `/api/v1/agent/sessions/:sessionId/messages` | send a new user message |
| `GET` | `/api/v1/agent/sessions/:sessionId/tool-traces` | fetch auditable tool usage |
| `POST` | `/api/v1/agent/approvals/:approvalId/decision` | approve or reject a sensitive action |
| `GET` or `WS` | `/api/v1/agent/sessions/:sessionId/stream` | stream assistant tokens, tool status, and approvals |

Recommended session shape:

```json
{
  "id": "agt-session-001",
  "userId": "operator-03",
  "status": "active",
  "createdAt": "2026-03-07T05:20:00.000Z",
  "updatedAt": "2026-03-07T05:21:12.000Z"
}
```

Recommended message create request:

```json
{
  "content": "Summarize critical alerts from the last 2 hours",
  "context": {
    "siteId": "site-hcm-01",
    "cameraIds": ["cam-hcm-01-01", "cam-hcm-01-02"]
  }
}
```

Recommended streamed event types:

- `message.delta`
- `message.completed`
- `tool.started`
- `tool.completed`
- `approval.required`
- `approval.resolved`
- `error`

Recommendation:

- keep provider-specific agent logic behind `services/agent`
- log all tool invocations with `userId`, `sessionId`, `toolName`, timestamp, and outcome

## Recommended Error Conventions

This is also `Recommended`, because the repo does not define a shared error envelope yet.

Recommended error payload:

```json
{
  "error": {
    "code": "INCIDENT_NOT_FOUND",
    "message": "Incident inc-9999 was not found",
    "requestId": "req_01JXYZ",
    "details": null
  }
}
```

Recommended status code usage:

- `400` for invalid query/body params
- `401` for missing auth
- `403` for authenticated but forbidden access
- `404` for missing resources
- `409` for conflict or invalid state transitions
- `422` for semantically invalid requests
- `500` for unexpected server failures

## Implementation Guidance For Replacing Mocks

### Keep stable

- `VmsApiClient` method names and return shapes
- `RealtimeEvent` payload shape
- query key structure in `apps/web/src/lib/api.ts`
- route-level ownership of data fetching

### Replace

- swap `mockApiClient` for a real HTTP implementation inside `packages/api-client`
- swap `MockRealtimeEventSocket` for a real WebSocket or SSE adapter
- move filtering, overview aggregation, and playback search from generated mock logic to the backend

### Example adapter shape

```ts
import type {
  AlertFilter,
  PlaybackSearchParams,
  VmsApiClient,
} from "@qaongdur/types";

export class HttpVmsApiClient implements VmsApiClient {
  async listSites() {
    return this.get("/api/v1/sites");
  }

  async listCameras(siteId?: string) {
    return this.get("/api/v1/cameras", { siteId });
  }

  async listLiveTiles(siteId?: string) {
    return this.get("/api/v1/live-tiles", { siteId });
  }

  async getOverview(siteId?: string) {
    return this.get("/api/v1/overview", { siteId });
  }

  async listAlerts(filter?: AlertFilter) {
    return this.get("/api/v1/alerts", filter);
  }

  async listIncidents() {
    return this.get("/api/v1/incidents");
  }

  async getIncidentById(id: string) {
    return this.get(`/api/v1/incidents/${id}`);
  }

  async searchPlayback(params: PlaybackSearchParams) {
    return this.post("/api/v1/playback/search", params);
  }

  async listDevices(siteId?: string) {
    return this.get("/api/v1/devices", { siteId });
  }

  private async get(path: string, query?: Record<string, unknown>) {
    void path;
    void query;
    throw new Error("Implement HTTP adapter");
  }

  private async post(path: string, body: unknown) {
    void path;
    void body;
    throw new Error("Implement HTTP adapter");
  }
}
```

## Source References

- `packages/types/src/index.ts`
- `packages/api-client/src/index.ts`
- `packages/api-client/src/mock-api-client.ts`
- `packages/api-client/src/mock-event-socket.ts`
- `packages/api-client/src/mock-data.ts`
- `apps/web/src/lib/api.ts`
- `apps/web/src/app/operator-layout.tsx`
- `apps/web/src/pages/*.tsx`
- `docs/codex-prompts/03-backend-vms-ai-platform.md`
- `docs/codex-prompts/04-agent-chat-openclaw.md`
