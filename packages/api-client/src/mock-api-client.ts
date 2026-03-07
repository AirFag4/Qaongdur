import type {
  AlertEvent,
  AlertFilter,
  Camera,
  CreateCameraInput,
  PlaybackSearchParams,
  PlaybackSegment,
  VmsApiClient,
} from "@qaongdur/types";
import { mockData } from "./mock-data";

const networkDelay = () => 140 + Math.round(Math.random() * 220);
const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

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
}

export const mockApiClient = new MockVmsApiClient();
