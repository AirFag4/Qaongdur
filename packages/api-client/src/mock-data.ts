import type {
  AlertEvent,
  AlertSeverity,
  Camera,
  Device,
  EvidenceClip,
  HealthStatus,
  Incident,
  IncidentTimelineItem,
  LiveStreamTile,
  Site,
} from "@qaongdur/types";

const zones = [
  "North Gate",
  "Loading Dock",
  "Parking East",
  "Main Lobby",
  "Warehouse Aisle 2",
  "Roof Access",
  "Perimeter South",
  "Shipping Bay",
];

const siteCatalog: Site[] = [
  { id: "site-hcm-01", code: "HCM-01", name: "Saigon Hub", region: "VN-South" },
  { id: "site-bkk-01", code: "BKK-01", name: "Bangkok Port", region: "TH-Central" },
  { id: "site-dad-01", code: "DAD-01", name: "Da Nang Yard", region: "VN-Central" },
];

const seeded = (seed: number) => Math.abs(Math.sin(seed * 987.31));

const healthFromSeed = (seed: number): HealthStatus => {
  const x = seeded(seed);
  if (x < 0.08) {
    return "offline";
  }
  if (x < 0.22) {
    return "critical";
  }
  if (x < 0.46) {
    return "warning";
  }
  return "healthy";
};

const severityFromSeed = (seed: number): AlertSeverity => {
  const x = seeded(seed);
  if (x < 0.2) {
    return "critical";
  }
  if (x < 0.45) {
    return "high";
  }
  if (x < 0.75) {
    return "medium";
  }
  return "low";
};

const minutesAgoIso = (minutes: number) =>
  new Date(Date.now() - minutes * 60 * 1000).toISOString();

const cameraCatalog: Camera[] = siteCatalog.flatMap((site, siteIndex) =>
  Array.from({ length: 12 }, (_, cameraIndex) => {
    const idx = siteIndex * 100 + cameraIndex;
    return {
      id: `cam-${site.code.toLowerCase()}-${String(cameraIndex + 1).padStart(2, "0")}`,
      siteId: site.id,
      name: `${site.code} Camera ${String(cameraIndex + 1).padStart(2, "0")}`,
      zone: zones[cameraIndex % zones.length],
      streamUrl: `rtsp://stream.${site.code.toLowerCase()}.vms.local/${cameraIndex + 1}`,
      health: healthFromSeed(idx),
      fps: 20 + (cameraIndex % 3) * 5,
      resolution: cameraIndex % 2 ? "1920x1080" : "2560x1440",
      uptimePct: Number((95 + seeded(idx + 9) * 5).toFixed(2)),
      lastSeenAt: minutesAgoIso(Math.floor(seeded(idx + 7) * 18)),
      tags: [
        cameraIndex % 2 ? "outdoor" : "indoor",
        cameraIndex % 3 ? "ptz" : "fixed",
      ],
    } satisfies Camera;
  }),
);

const liveTileCatalog: LiveStreamTile[] = cameraCatalog.map((camera, index) => {
  const detectionCount = Math.floor(seeded(index + 3) * 3);
  return {
    cameraId: camera.id,
    isLive: camera.health !== "offline",
    latencyMs: Math.floor(120 + seeded(index + 20) * 450),
    bitrateKbps: Math.floor(2200 + seeded(index + 40) * 2800),
    detections: Array.from({ length: detectionCount }, (_, boxIndex) => ({
      id: `${camera.id}-box-${boxIndex + 1}`,
      label: boxIndex % 2 ? "Vehicle" : "Person",
      confidence: Number((0.62 + seeded(index + boxIndex + 55) * 0.35).toFixed(2)),
      severity: severityFromSeed(index + boxIndex + 88),
      x: Math.floor(10 + seeded(index + boxIndex + 12) * 60),
      y: Math.floor(12 + seeded(index + boxIndex + 21) * 52),
      width: Math.floor(16 + seeded(index + boxIndex + 32) * 28),
      height: Math.floor(18 + seeded(index + boxIndex + 14) * 32),
    })),
  };
});

const alertTitles = [
  "Perimeter breach",
  "Loitering detected",
  "Restricted zone entry",
  "Object left unattended",
  "Vehicle wrong-way movement",
  "Camera tamper suspected",
];

const alertSummaries = [
  "Movement pattern exceeded configured dwell threshold.",
  "Detection crossed forbidden polygon near cargo lane.",
  "AI tracker flagged repeated entry attempts.",
  "New object remained static for over 6 minutes.",
  "Direction vector reversed against lane policy.",
  "Lens obstruction confidence exceeded threshold.",
];

const alertCatalog: AlertEvent[] = Array.from({ length: 48 }, (_, index) => {
  const camera = cameraCatalog[index % cameraCatalog.length];
  const severity = severityFromSeed(index + 200);
  const statuses = ["new", "acknowledged", "investigating", "resolved"] as const;
  return {
    id: `alt-${String(index + 1).padStart(4, "0")}`,
    cameraId: camera.id,
    siteId: camera.siteId,
    title: alertTitles[index % alertTitles.length],
    summary: alertSummaries[index % alertSummaries.length],
    rule: `rule-${(index % 9) + 1}`,
    severity,
    status: statuses[index % statuses.length],
    confidence: Number((0.58 + seeded(index + 67) * 0.4).toFixed(2)),
    happenedAt: minutesAgoIso(index * 13 + Math.floor(seeded(index + 122) * 6)),
  };
});

const evidenceForIncident = (
  incidentId: string,
  cameraIds: string[],
  offset: number,
): EvidenceClip[] =>
  cameraIds.slice(0, 3).map((cameraId, index) => {
    const startOffset = offset + index * 18;
    const startAt = minutesAgoIso(startOffset);
    const endAt = minutesAgoIso(Math.max(startOffset - 3, 1));
    return {
      id: `${incidentId}-ev-${index + 1}`,
      cameraId,
      title: `Evidence Clip ${index + 1}`,
      type: index % 2 ? "snapshot" : "video",
      startAt,
      endAt,
      durationSec: 180,
      storageRef: `s3://qaongdur/evidence/${incidentId}/${index + 1}`,
    };
  });

const timelineForIncident = (
  incidentId: string,
  offset: number,
): IncidentTimelineItem[] => [
  {
    id: `${incidentId}-t-1`,
    happenedAt: minutesAgoIso(offset + 46),
    actor: "AI Engine",
    action: "Incident opened",
    note: "Alert cluster matched high-priority scenario.",
  },
  {
    id: `${incidentId}-t-2`,
    happenedAt: minutesAgoIso(offset + 31),
    actor: "Operator 03",
    action: "Assigned owner",
    note: "Escalated to shift supervisor for verification.",
  },
  {
    id: `${incidentId}-t-3`,
    happenedAt: minutesAgoIso(offset + 15),
    actor: "Supervisor",
    action: "Evidence requested",
    note: "Requested synchronized clips from adjacent cameras.",
  },
];

const incidentCatalog: Incident[] = [
  {
    id: "inc-1001",
    title: "Perimeter fence breach near Dock 2",
    siteId: siteCatalog[0].id,
    severity: "critical",
    status: "investigating",
    openedAt: minutesAgoIso(96),
    cameraIds: [cameraCatalog[0].id, cameraCatalog[1].id, cameraCatalog[2].id],
    owner: "Nguyen T.",
    summary:
      "Multiple motion vectors crossed the north perimeter after access hours.",
    tags: ["perimeter", "after-hours", "dock-2"],
    timeline: timelineForIncident("inc-1001", 20),
    evidence: evidenceForIncident(
      "inc-1001",
      [cameraCatalog[0].id, cameraCatalog[1].id, cameraCatalog[2].id],
      65,
    ),
  },
  {
    id: "inc-1002",
    title: "Vehicle entered restricted loading lane",
    siteId: siteCatalog[1].id,
    severity: "high",
    status: "triaging",
    openedAt: minutesAgoIso(210),
    cameraIds: [cameraCatalog[13].id, cameraCatalog[14].id, cameraCatalog[15].id],
    owner: "A. Chaiyasit",
    summary:
      "Object tracker identified a reverse route crossing marked hazard lane.",
    tags: ["vehicle", "loading", "lane-violation"],
    timeline: timelineForIncident("inc-1002", 128),
    evidence: evidenceForIncident(
      "inc-1002",
      [cameraCatalog[13].id, cameraCatalog[14].id, cameraCatalog[15].id],
      178,
    ),
  },
  {
    id: "inc-1003",
    title: "Unattended package at west lobby",
    siteId: siteCatalog[2].id,
    severity: "medium",
    status: "open",
    openedAt: minutesAgoIso(320),
    cameraIds: [cameraCatalog[25].id, cameraCatalog[26].id, cameraCatalog[27].id],
    owner: "Tran H.",
    summary:
      "Persistent object detector tracked static object for > 7 minutes in lobby.",
    tags: ["object", "lobby", "screening"],
    timeline: timelineForIncident("inc-1003", 211),
    evidence: evidenceForIncident(
      "inc-1003",
      [cameraCatalog[25].id, cameraCatalog[26].id, cameraCatalog[27].id],
      270,
    ),
  },
  {
    id: "inc-1004",
    title: "Camera tamper signal on warehouse lane",
    siteId: siteCatalog[0].id,
    severity: "high",
    status: "resolved",
    openedAt: minutesAgoIso(710),
    closedAt: minutesAgoIso(520),
    cameraIds: [cameraCatalog[5].id],
    owner: "Nguyen T.",
    summary: "Abrupt contrast delta triggered tamper detector and health downgrade.",
    tags: ["tamper", "maintenance"],
    timeline: timelineForIncident("inc-1004", 611),
    evidence: evidenceForIncident("inc-1004", [cameraCatalog[5].id], 670),
  },
];

const deviceCatalog: Device[] = [
  ...cameraCatalog.map(
    (camera): Device => ({
      id: `dev-${camera.id}`,
      cameraId: camera.id,
      siteId: camera.siteId,
      name: camera.name,
      type: "camera",
      model: camera.tags.includes("ptz") ? "Axis Q6225-LE" : "Hikvision DS-2CD",
      ipAddress: `10.${Math.floor(seeded(camera.id.length) * 10 + 10)}.${Math.floor(
        seeded(camera.id.length + 1) * 50 + 10,
      )}.${Math.floor(seeded(camera.id.length + 2) * 120 + 10)}`,
      firmware: "v5.9.7",
      health: camera.health,
      lastHeartbeatAt: camera.lastSeenAt,
      uptimePct: camera.uptimePct,
      packetLossPct: Number((seeded(camera.id.length + 22) * 4).toFixed(2)),
      tags: [...camera.tags],
    }),
  ),
  ...siteCatalog.flatMap((site, idx) => [
    {
      id: `dev-${site.code.toLowerCase()}-nvr`,
      siteId: site.id,
      name: `${site.code} NVR`,
      type: "nvr",
      model: "Synology DVA3221",
      ipAddress: `172.16.${20 + idx}.20`,
      firmware: "v2.3.1",
      health: idx % 2 ? "healthy" : "warning",
      lastHeartbeatAt: minutesAgoIso(4 + idx * 2),
      uptimePct: 99.12,
      packetLossPct: Number((0.1 + seeded(idx + 30)).toFixed(2)),
      tags: ["recording", "rack"],
    } satisfies Device,
    {
      id: `dev-${site.code.toLowerCase()}-gw`,
      siteId: site.id,
      name: `${site.code} Gateway`,
      type: "gateway",
      model: "EdgeLink XL",
      ipAddress: `172.16.${20 + idx}.42`,
      firmware: "v1.8.4",
      health: "healthy",
      lastHeartbeatAt: minutesAgoIso(2 + idx),
      uptimePct: 99.74,
      packetLossPct: Number((0.04 + seeded(idx + 40)).toFixed(2)),
      tags: ["edge", "bridge"],
    } satisfies Device,
  ]),
];

export const mockData = {
  sites: siteCatalog,
  cameras: cameraCatalog,
  liveTiles: liveTileCatalog,
  alerts: alertCatalog,
  incidents: incidentCatalog,
  devices: deviceCatalog,
};
