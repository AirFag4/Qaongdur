import type {
  AlertEvent,
  AlertFilter,
  Camera,
  CropTrack,
  CropTrackFilter,
  CreateCameraInput,
  PlaybackSearchParams,
  PlaybackSegment,
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
    id: "source-people-walking",
    siteId: "site-local-01",
    cameraId: "cam-people-walking",
    cameraName: "People Walking",
    filePath: "/mock-videos/people-walking.mp4",
    durationSec: 44,
    frameWidth: 1280,
    frameHeight: 720,
    sourceFps: 24,
    trackCount: 2,
  },
  {
    id: "source-vehicles",
    siteId: "site-local-01",
    cameraId: "cam-vehicles",
    cameraName: "Vehicles",
    filePath: "/mock-videos/vehicles.mp4",
    durationSec: 35,
    frameWidth: 1280,
    frameHeight: 720,
    sourceFps: 30,
    trackCount: 2,
  },
];

const mockCropTracks: CropTrack[] = [
  {
    id: "trk-mock-person-1",
    sourceId: "source-people-walking",
    siteId: "site-local-01",
    cameraId: "cam-people-walking",
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
    frameCount: 9,
    sampleFps: 2,
    maxConfidence: 0.94,
    avgConfidence: 0.88,
    embeddingStatus: "fallback",
    embeddingModel: "histogram-fallback",
    faceStatus: "unavailable",
    faceModel: "InspireFace-small",
    closedReason: "track-gap",
    firstCropDataUrl: createSvgDataUrl("person first", 205),
    middleCropDataUrl: createSvgDataUrl("person mid", 215),
    lastCropDataUrl: createSvgDataUrl("person last", 225),
  },
  {
    id: "trk-mock-vehicle-1",
    sourceId: "source-vehicles",
    siteId: "site-local-01",
    cameraId: "cam-vehicles",
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
    frameCount: 12,
    sampleFps: 2,
    maxConfidence: 0.97,
    avgConfidence: 0.91,
    embeddingStatus: "fallback",
    embeddingModel: "histogram-fallback",
    faceStatus: "skipped-label",
    faceModel: "InspireFace-small",
    closedReason: "end-of-source",
    firstCropDataUrl: createSvgDataUrl("vehicle first", 26),
    middleCropDataUrl: createSvgDataUrl("vehicle mid", 36),
    lastCropDataUrl: createSvgDataUrl("vehicle last", 46),
  },
];

const matchesSearch = (alert: AlertEvent, query?: string) => {
  if (!query?.trim()) {
    return true;
  }
  const text = `${alert.title} ${alert.summary} ${alert.rule}`.toLowerCase();
  return text.includes(query.toLowerCase());
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
      health: "warning",
      fps: 0,
      resolution: "Unknown",
      uptimePct: 0,
      lastSeenAt: new Date().toISOString(),
      tags: ["rtsp", "mock"],
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
      detector: {
        available: true,
        modelName: "mock-detector",
        detail: "Mock pipeline status",
      },
      embedding: {
        modelName: "histogram-fallback",
      },
      face: {
        enabled: true,
        modelName: "InspireFace-small",
      },
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

  async listCropTracks(filter?: CropTrackFilter): Promise<CropTrack[]> {
    await sleep(networkDelay());
    return mockCropTracks.filter((track) => {
      if (filter?.sourceId && track.sourceId !== filter.sourceId) {
        return false;
      }
      if (filter?.label && filter.label !== "all" && track.label !== filter.label) {
        return false;
      }
      return true;
    });
  }
}

export const mockApiClient = new MockVmsApiClient();
