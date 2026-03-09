import type {
  AlertEvent,
  AlertFilter,
  Camera,
  CropTrackDetail,
  CropTrack,
  CropTrackFilter,
  CropTrackPage,
  CreateCameraInput,
  PlaybackSearchParams,
  PlaybackSegment,
  SystemSettings,
  VmsApiClient,
  VisionJobStatus,
  VisionPipelineStatus,
  VisionSource,
} from "@qaongdur/types";
import { mockData } from "./mock-data";

const networkDelay = () => 140 + Math.round(Math.random() * 220);
const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

const createSvgDataUrl = (label: string, hue: number) =>
  `data:image/svg+xml;utf8,${encodeURIComponent(
    `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 240 320">
      <defs>
        <linearGradient id="bg" x1="0" x2="1" y1="0" y2="1">
          <stop offset="0%" stop-color="hsl(${hue},70%,32%)"/>
          <stop offset="100%" stop-color="hsl(${(hue + 40) % 360},60%,18%)"/>
        </linearGradient>
      </defs>
      <rect width="240" height="320" fill="url(#bg)"/>
      <rect x="28" y="44" width="184" height="232" rx="18" fill="rgba(0,0,0,0.22)" stroke="rgba(255,255,255,0.28)"/>
      <text x="120" y="166" text-anchor="middle" fill="#f5f5f4" font-family="monospace" font-size="24">${label}</text>
    </svg>`,
  )}`;

const mockVisionSources: VisionSource[] = [
  {
    id: "cam-mock-video-people-walking",
    siteId: "site-local-01",
    cameraId: "cam-mock-video-people-walking",
    cameraName: "People Walking",
    pathName: "mock-video-people-walking",
    relayRtspUrl: "rtsp://mediamtx:8554/mock-video-people-walking",
    liveStreamUrl: "http://localhost:8888/mock-video-people-walking/index.m3u8",
    sourceKind: "mock-video",
    ingestMode: "push",
    health: "healthy",
    trackCount: 2,
    processedSegmentCount: 4,
    latestProcessedAt: new Date(Date.now() - 30_000).toISOString(),
    lastSegmentAt: new Date(Date.now() - 30_000).toISOString(),
  },
  {
    id: "cam-mock-video-vehicles",
    siteId: "site-local-01",
    cameraId: "cam-mock-video-vehicles",
    cameraName: "Vehicles",
    pathName: "mock-video-vehicles",
    relayRtspUrl: "rtsp://mediamtx:8554/mock-video-vehicles",
    liveStreamUrl: "http://localhost:8888/mock-video-vehicles/index.m3u8",
    sourceKind: "mock-video",
    ingestMode: "push",
    health: "healthy",
    trackCount: 2,
    processedSegmentCount: 5,
    latestProcessedAt: new Date(Date.now() - 15_000).toISOString(),
    lastSegmentAt: new Date(Date.now() - 15_000).toISOString(),
  },
];

const mockCropTracks: CropTrack[] = [
  {
    id: "trk-mock-person-1",
    sourceId: "cam-mock-video-people-walking",
    siteId: "site-local-01",
    cameraId: "cam-mock-video-people-walking",
    cameraName: "People Walking",
    label: "person",
    detectorLabel: "person",
    firstSeenAt: new Date().toISOString(),
    middleSeenAt: new Date().toISOString(),
    lastSeenAt: new Date().toISOString(),
    firstSeenOffsetMs: 4000,
    middleSeenOffsetMs: 8200,
    lastSeenOffsetMs: 12800,
    firstSeenOffsetLabel: "00:00:04.000",
    middleSeenOffsetLabel: "00:00:08.200",
    lastSeenOffsetLabel: "00:00:12.800",
    segmentPath: "/recordings/mock-video-people-walking/2026-03-08_12-00-00-000000.mp4",
    segmentStartAt: new Date(Date.now() - 60_000).toISOString(),
    segmentDurationSec: 60,
    frameCount: 9,
    sampleFps: 2,
    maxConfidence: 0.94,
    avgConfidence: 0.88,
    embeddingStatus: "fallback",
    embeddingModel: "histogram-fallback",
    embeddingDim: 64,
    faceStatus: "ready",
    faceModel: "InspireFace-small",
    faceDim: 512,
    closedReason: "track-gap",
    firstPoint: { x: 82, y: 110 },
    middlePoint: { x: 118, y: 128 },
    lastPoint: { x: 151, y: 139 },
    firstCropDataUrl: createSvgDataUrl("person first", 205),
    middleCropDataUrl: createSvgDataUrl("person mid", 215),
    lastCropDataUrl: createSvgDataUrl("person last", 225),
  },
  {
    id: "trk-mock-vehicle-1",
    sourceId: "cam-mock-video-vehicles",
    siteId: "site-local-01",
    cameraId: "cam-mock-video-vehicles",
    cameraName: "Vehicles",
    label: "vehicle",
    detectorLabel: "car",
    firstSeenAt: new Date().toISOString(),
    middleSeenAt: new Date().toISOString(),
    lastSeenAt: new Date().toISOString(),
    firstSeenOffsetMs: 2000,
    middleSeenOffsetMs: 6900,
    lastSeenOffsetMs: 14000,
    firstSeenOffsetLabel: "00:00:02.000",
    middleSeenOffsetLabel: "00:00:06.900",
    lastSeenOffsetLabel: "00:00:14.000",
    segmentPath: "/recordings/mock-video-vehicles/2026-03-08_12-01-00-000000.mp4",
    segmentStartAt: new Date(Date.now() - 30_000).toISOString(),
    segmentDurationSec: 60,
    frameCount: 12,
    sampleFps: 2,
    maxConfidence: 0.97,
    avgConfidence: 0.91,
    embeddingStatus: "fallback",
    embeddingModel: "histogram-fallback",
    embeddingDim: 64,
    faceStatus: "skipped-label",
    faceModel: "InspireFace-small",
    faceDim: null,
    closedReason: "end-of-source",
    firstPoint: { x: 73, y: 143 },
    middlePoint: { x: 136, y: 152 },
    lastPoint: { x: 190, y: 164 },
    firstCropDataUrl: createSvgDataUrl("vehicle first", 26),
    middleCropDataUrl: createSvgDataUrl("vehicle mid", 36),
    lastCropDataUrl: createSvgDataUrl("vehicle last", 46),
  },
];

const mockSystemSettings: SystemSettings = {
  checkedAt: new Date().toISOString(),
  auth: {
    issuer: "http://localhost:8080/realms/qaongdur-dev",
    audience: "qaongdur-control-api",
    stepUpAcr: "urn:qaongdur:loa:2",
    user: {
      id: "user-mock-admin",
      username: "pat.admin",
      displayName: "Pat Admin",
      email: "pat.admin@example.com",
      roles: ["platform-admin"],
      acr: "urn:qaongdur:loa:1",
    },
  },
  recording: {
    segmentDurationSeconds: 60,
    playbackPublicUrl: "http://localhost:9996",
    hlsPublicUrl: "http://localhost:8888",
  },
  vision: {
    serviceUrl: "http://localhost:8010",
    autoIngest: true,
    notes: [
      "Mock settings payload for offline UI development.",
      "Real runtime settings are env-backed in the backend stack.",
    ],
  },
};

const matchesSearch = (alert: AlertEvent, query?: string) => {
  if (!query?.trim()) {
    return true;
  }
  const text = `${alert.title} ${alert.summary} ${alert.rule}`.toLowerCase();
  return text.includes(query.toLowerCase());
};

const toCropTrackSummary = (track: CropTrack): CropTrack => {
  const { firstCropDataUrl: _firstCropDataUrl, lastCropDataUrl: _lastCropDataUrl, ...summary } = track;
  return summary;
};

export class MockVmsApiClient implements VmsApiClient {
  async listSites() {
    await sleep(networkDelay());
    return mockData.sites;
  }

  async listCameras(siteId?: string) {
    await sleep(networkDelay());
    return siteId
      ? mockData.cameras.filter((camera) => camera.siteId === siteId)
      : mockData.cameras;
  }

  async createCamera(input: CreateCameraInput): Promise<Camera> {
    await sleep(networkDelay());
    const siteId = input.siteId ?? mockData.sites[0]?.id ?? "site-local-01";
    const camera: Camera = {
      id: `cam-local-${Date.now()}`,
      siteId,
      name: input.name,
      zone: input.zone,
      streamUrl: input.rtspUrl,
      liveStreamUrl: null,
      playbackPath: null,
      rtspTransport: input.rtspTransport ?? "automatic",
      rtspAnyPort: input.rtspAnyPort ?? false,
      health: "warning",
      fps: 0,
      resolution: "Unknown",
      uptimePct: 0,
      lastSeenAt: new Date().toISOString(),
      tags: [
        "rtsp",
        "mock",
        `rtsp-${input.rtspTransport ?? "automatic"}`,
        ...(input.rtspAnyPort ? ["rtsp-any-port"] : []),
      ],
    };

    mockData.cameras.unshift(camera);
    mockData.liveTiles.unshift({
      cameraId: camera.id,
      isLive: false,
      latencyMs: 0,
      bitrateKbps: 0,
      detections: [],
      hlsUrl: null,
    });
    mockData.devices.unshift({
      id: `dev-${camera.id}`,
      cameraId: camera.id,
      siteId,
      name: input.name,
      type: "camera",
      model: "RTSP Camera",
      ipAddress: "mock.local",
      firmware: "mock",
      health: "warning",
      lastHeartbeatAt: camera.lastSeenAt,
      uptimePct: 0,
      packetLossPct: 0,
      tags: ["rtsp", "mock"],
    });

    return camera;
  }

  async reconnectCamera(cameraId: string): Promise<Camera> {
    await sleep(networkDelay());
    const camera = mockData.cameras.find((item) => item.id === cameraId);
    if (!camera) {
      throw new Error(`Camera ${cameraId} was not found.`);
    }

    camera.health = "warning";
    camera.lastSeenAt = new Date().toISOString();

    const device = mockData.devices.find((item) => item.cameraId === cameraId);
    if (device) {
      device.health = "warning";
      device.lastHeartbeatAt = camera.lastSeenAt;
    }

    return camera;
  }

  async deleteCamera(cameraId: string): Promise<void> {
    await sleep(networkDelay());
    mockData.cameras = mockData.cameras.filter((camera) => camera.id !== cameraId);
    mockData.liveTiles = mockData.liveTiles.filter((tile) => tile.cameraId !== cameraId);
    mockData.devices = mockData.devices.filter((device) => device.cameraId !== cameraId);
    mockData.alerts = mockData.alerts.filter((alert) => alert.cameraId !== cameraId);
    mockData.incidents = mockData.incidents.filter(
      (incident) => !incident.cameraIds.includes(cameraId),
    );
  }

  async listLiveTiles(siteId?: string) {
    await sleep(networkDelay());
    if (!siteId) {
      return mockData.liveTiles;
    }
    const siteCameraIds = new Set(
      mockData.cameras
        .filter((camera) => camera.siteId === siteId)
        .map((camera) => camera.id),
    );
    return mockData.liveTiles.filter((tile) => siteCameraIds.has(tile.cameraId));
  }

  async getOverview(siteId?: string) {
    await sleep(networkDelay());
    const cameraScope = siteId
      ? mockData.cameras.filter((camera) => camera.siteId === siteId)
      : mockData.cameras;
    const cameraIds = new Set(cameraScope.map((camera) => camera.id));
    const scopedAlerts = mockData.alerts.filter((alert) =>
      cameraIds.has(alert.cameraId),
    );
    const scopedIncidents = mockData.incidents.filter((incident) =>
      incident.cameraIds.some((cameraId) => cameraIds.has(cameraId)),
    );
    const scopedTiles = mockData.liveTiles.filter((tile) =>
      cameraIds.has(tile.cameraId),
    );

    const liveCount = scopedTiles.filter((tile) => tile.isLive).length;
    const warningCount = cameraScope.filter(
      (camera) => camera.health === "warning" || camera.health === "critical",
    ).length;
    const criticalAlerts = scopedAlerts.filter(
      (alert) => alert.severity === "critical",
    ).length;

    const streamHealth = [
      { label: "Healthy", value: cameraScope.filter((c) => c.health === "healthy").length },
      { label: "Warning", value: cameraScope.filter((c) => c.health === "warning").length },
      { label: "Critical", value: cameraScope.filter((c) => c.health === "critical").length },
      { label: "Offline", value: cameraScope.filter((c) => c.health === "offline").length },
    ];

    return {
      metrics: [
        {
          label: "Live Streams",
          value: `${liveCount}/${cameraScope.length}`,
          delta: "+3.4% shift",
          trend: "up" as const,
        },
        {
          label: "Open Alerts",
          value: String(scopedAlerts.filter((a) => a.status !== "resolved").length),
          delta: `${criticalAlerts} critical`,
          trend: criticalAlerts ? ("up" as const) : ("flat" as const),
        },
        {
          label: "Active Incidents",
          value: String(scopedIncidents.filter((i) => i.status !== "resolved").length),
          delta: "-1 since 12:00",
          trend: "down" as const,
        },
        {
          label: "Watchlist Cameras",
          value: String(warningCount),
          delta: "Needs review",
          trend: warningCount ? ("up" as const) : ("flat" as const),
        },
      ],
      topAlerts: scopedAlerts.slice(0, 8),
      activeIncidents: scopedIncidents.slice(0, 4),
      streamHealth,
    };
  }

  async listAlerts(filter?: AlertFilter) {
    await sleep(networkDelay());
    return mockData.alerts.filter((alert) => {
      if (filter?.siteId && alert.siteId !== filter.siteId) {
        return false;
      }
      if (filter?.cameraId && alert.cameraId !== filter.cameraId) {
        return false;
      }
      if (filter?.severity && filter.severity !== "all" && alert.severity !== filter.severity) {
        return false;
      }
      if (filter?.status && filter.status !== "all" && alert.status !== filter.status) {
        return false;
      }
      return matchesSearch(alert, filter?.search);
    });
  }

  async listIncidents() {
    await sleep(networkDelay());
    return mockData.incidents;
  }

  async getIncidentById(id: string) {
    await sleep(networkDelay());
    return mockData.incidents.find((incident) => incident.id === id);
  }

  async searchPlayback(params: PlaybackSearchParams): Promise<PlaybackSegment[]> {
    await sleep(networkDelay());
    const from = new Date(params.from).getTime();
    const to = new Date(params.to).getTime();
    const cameras = params.cameraIds.length
      ? params.cameraIds
      : mockData.cameras.slice(0, 6).map((camera) => camera.id);

    const bucketMs = 15 * 60 * 1000;
    const totalBuckets = Math.max(4, Math.min(40, Math.floor((to - from) / bucketMs)));

    return Array.from({ length: totalBuckets }, (_, index) => {
      const start = from + index * bucketMs;
      const end = start + bucketMs;
      const cameraId = cameras[index % cameras.length];
      const base = Math.abs(Math.sin(index * 9.1 + cameraId.length));

      return {
        id: `seg-${cameraId}-${index + 1}`,
        cameraId,
        startAt: new Date(start).toISOString(),
        endAt: new Date(end).toISOString(),
        alerts: Math.floor(base * 5),
        motionScore: Number((0.15 + base * 0.85).toFixed(2)),
        durationSec: (end - start) / 1000,
        playbackUrl: `http://localhost:9996/get?path=${encodeURIComponent(cameraId)}&start=${encodeURIComponent(new Date(start).toISOString())}&duration=${(end - start) / 1000}`,
        downloadUrl: `http://localhost:9996/get?path=${encodeURIComponent(cameraId)}&start=${encodeURIComponent(new Date(start).toISOString())}&duration=${(end - start) / 1000}&format=mp4`,
      };
    });
  }

  async listDevices(siteId?: string) {
    await sleep(networkDelay());
    return siteId
      ? mockData.devices.filter((device) => device.siteId === siteId)
      : mockData.devices;
  }

  async listVisionSources(): Promise<VisionSource[]> {
    await sleep(networkDelay());
    return mockVisionSources;
  }

  async getVisionStatus(): Promise<VisionPipelineStatus> {
    await sleep(networkDelay());
    const latestJob: VisionJobStatus = {
      id: "job-mock-1",
      status: "completed",
      sourceIds: mockVisionSources.map((source) => source.id),
      sampledFps: 2,
      trackCount: mockCropTracks.length,
      startedAt: new Date(Date.now() - 30_000).toISOString(),
      finishedAt: new Date(Date.now() - 5_000).toISOString(),
      detail: null,
    };
    return {
      sampleMode: true,
      autoIngest: true,
      detector: {
        available: true,
        modelName: "mock-detector",
        detail: "Mock pipeline status",
      },
      embedding: {
        modelName: "histogram-fallback",
      },
      face: {
        available: true,
        enabled: true,
        mode: "remote",
        modelName: "InspireFace-small",
        detail: "Mock face service status.",
      },
      vectorStore: {
        enabled: true,
        available: true,
        provider: "qdrant",
        detail: "Mock vector store connected.",
      },
      sourceSync: {
        lastSyncedAt: new Date(Date.now() - 5_000).toISOString(),
        error: null,
      },
      queueDepth: 0,
      sampleFps: 2,
      latestJob,
      storage: {
        usedBytes: 512_000,
        limitBytes: 10 * 1024 * 1024 * 1024,
        artifactCount: mockCropTracks.length * 3,
        freeBytes: 10 * 1024 * 1024 * 1024 - 512_000,
      },
    };
  }

  async runVisionMockJob(sourceIds?: string[]): Promise<VisionJobStatus> {
    await sleep(networkDelay());
    return {
      id: `job-mock-${Date.now()}`,
      status: "running",
      sourceIds: sourceIds?.length ? sourceIds : mockVisionSources.map((source) => source.id),
      sampledFps: 2,
      trackCount: 0,
      startedAt: new Date().toISOString(),
      finishedAt: null,
      detail: null,
    };
  }

  async listCropTracks(filter?: CropTrackFilter): Promise<CropTrackPage> {
    await sleep(networkDelay());
    const filtered = mockCropTracks.filter((track) => {
      if (filter?.sourceId && track.sourceId !== filter.sourceId) {
        return false;
      }
      if (filter?.cameraId && track.cameraId !== filter.cameraId) {
        return false;
      }
      if (filter?.label && filter.label !== "all" && track.label !== filter.label) {
        return false;
      }
      if (filter?.fromAt && new Date(track.lastSeenAt).getTime() < new Date(filter.fromAt).getTime()) {
        return false;
      }
      if (filter?.toAt && new Date(track.firstSeenAt).getTime() > new Date(filter.toAt).getTime()) {
        return false;
      }
      return true;
    });
    const pageSize = Math.max(filter?.pageSize ?? 20, 1);
    const page = Math.max(filter?.page ?? 1, 1);
    const totalCount = filtered.length;
    const totalPages = Math.max(Math.ceil(totalCount / pageSize), 1);
    const safePage = Math.min(page, totalPages);
    const startIndex = (safePage - 1) * pageSize;
    return {
      tracks: filtered.slice(startIndex, startIndex + pageSize).map(toCropTrackSummary),
      totalCount,
      page: safePage,
      pageSize,
      totalPages,
    };
  }

  async getCropTrack(trackId: string): Promise<CropTrackDetail | undefined> {
    await sleep(networkDelay());
    const track = mockCropTracks.find((item) => item.id === trackId);
    if (!track) {
      return undefined;
    }
    return {
      ...track,
      firstCropDataUrl: track.firstCropDataUrl!,
      lastCropDataUrl: track.lastCropDataUrl!,
      firstBBox: [20, 40, 120, 220],
      middleBBox: [42, 48, 136, 228],
      lastBBox: [60, 52, 152, 236],
      createdAt: new Date(Date.now() - 25_000).toISOString(),
    };
  }

  async getSystemSettings(): Promise<SystemSettings> {
    await sleep(networkDelay());
    return mockSystemSettings;
  }
}

export const mockApiClient = new MockVmsApiClient();
