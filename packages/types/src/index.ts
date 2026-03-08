export type HealthStatus = "healthy" | "warning" | "critical" | "offline";
export type AlertSeverity = "low" | "medium" | "high" | "critical";
export type IncidentStatus =
  | "open"
  | "triaging"
  | "investigating"
  | "resolved";
export type AlertStatus = "new" | "acknowledged" | "investigating" | "resolved";
export type DeviceType = "camera" | "nvr" | "gateway" | "sensor";
export type PlatformRole =
  | "platform-admin"
  | "site-admin"
  | "operator"
  | "reviewer"
  | "viewer";

export interface AuthenticatedUser {
  id: string;
  username: string;
  displayName: string;
  email?: string;
  roles: PlatformRole[];
  acr?: string;
}

export interface AuthSession {
  accessToken: string;
  idToken?: string;
  expiresAt?: number;
  user: AuthenticatedUser;
}

export interface BackendAuthStatus {
  service: string;
  issuer: string;
  audience: string;
  checkedAt: string;
  user: AuthenticatedUser;
}

export interface ApprovalRequest {
  action: string;
  approvalPath: string[];
  rationale?: string;
  requiresStepUp: boolean;
}

export interface ApprovalResult extends ApprovalRequest {
  approved: boolean;
  approvedAt: string;
  approvedBy: string;
  stepUpSatisfied: boolean;
}

export interface Site {
  id: string;
  name: string;
  code: string;
  region: string;
}

export interface Camera {
  id: string;
  siteId: string;
  name: string;
  zone: string;
  streamUrl: string;
  liveStreamUrl?: string | null;
  playbackPath?: string | null;
  health: HealthStatus;
  fps: number;
  resolution: string;
  uptimePct: number;
  lastSeenAt: string;
  tags: string[];
}

export interface DetectionBox {
  id: string;
  label: string;
  confidence: number;
  severity: AlertSeverity;
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface LiveStreamTile {
  cameraId: string;
  isLive: boolean;
  latencyMs: number;
  bitrateKbps: number;
  detections: DetectionBox[];
  hlsUrl?: string | null;
}

export interface AlertEvent {
  id: string;
  cameraId: string;
  siteId: string;
  title: string;
  summary: string;
  rule: string;
  severity: AlertSeverity;
  status: AlertStatus;
  confidence: number;
  happenedAt: string;
}

export interface EvidenceClip {
  id: string;
  cameraId: string;
  title: string;
  type: "video" | "snapshot" | "report";
  startAt: string;
  endAt: string;
  durationSec: number;
  storageRef: string;
}

export interface IncidentTimelineItem {
  id: string;
  happenedAt: string;
  actor: string;
  action: string;
  note: string;
}

export interface Incident {
  id: string;
  title: string;
  siteId: string;
  severity: AlertSeverity;
  status: IncidentStatus;
  openedAt: string;
  closedAt?: string;
  cameraIds: string[];
  owner: string;
  summary: string;
  tags: string[];
  timeline: IncidentTimelineItem[];
  evidence: EvidenceClip[];
}

export interface PlaybackSegment {
  id: string;
  cameraId: string;
  startAt: string;
  endAt: string;
  alerts: number;
  motionScore: number;
  durationSec?: number;
  playbackUrl?: string;
}

export interface Device {
  id: string;
  cameraId?: string;
  siteId: string;
  name: string;
  type: DeviceType;
  model: string;
  ipAddress: string;
  firmware: string;
  health: HealthStatus;
  lastHeartbeatAt: string;
  uptimePct: number;
  packetLossPct: number;
}

export interface OverviewMetric {
  label: string;
  value: string;
  delta: string;
  trend: "up" | "down" | "flat";
}

export interface OverviewSnapshot {
  metrics: OverviewMetric[];
  topAlerts: AlertEvent[];
  activeIncidents: Incident[];
  streamHealth: { label: string; value: number }[];
}

export interface AlertFilter {
  siteId?: string;
  cameraId?: string;
  severity?: AlertSeverity | "all";
  status?: AlertStatus | "all";
  search?: string;
}

export interface PlaybackSearchParams {
  cameraIds: string[];
  from: string;
  to: string;
  includeAlerts: boolean;
}

export interface CreateCameraInput {
  siteId?: string;
  name: string;
  zone: string;
  rtspUrl: string;
}

export type VisionTrackLabel = "person" | "vehicle";

export interface VisionSource {
  id: string;
  siteId: string;
  cameraId: string;
  cameraName: string;
  filePath: string;
  durationSec: number;
  frameWidth: number;
  frameHeight: number;
  sourceFps: number;
  trackCount: number;
}

export interface VisionStorageStatus {
  usedBytes: number;
  limitBytes: number;
  artifactCount: number;
  freeBytes: number;
}

export interface VisionJobStatus {
  id: string;
  status: "running" | "completed" | "failed";
  sourceIds: string[];
  sampledFps: number;
  trackCount: number;
  startedAt: string;
  finishedAt?: string | null;
  detail?: string | null;
}

export interface VisionPipelineStatus {
  sampleMode: boolean;
  detector: {
    available: boolean;
    modelName: string;
    detail: string;
  };
  embedding: {
    modelName: string;
  };
  face: {
    enabled: boolean;
    modelName: string;
  };
  latestJob?: VisionJobStatus | null;
  storage: VisionStorageStatus;
}

export interface CropTrackFilter {
  sourceId?: string;
  label?: VisionTrackLabel | "all";
}

export interface CropTrack {
  id: string;
  sourceId: string;
  siteId: string;
  cameraId: string;
  cameraName: string;
  label: VisionTrackLabel;
  detectorLabel: string;
  firstSeenAt: string;
  middleSeenAt: string;
  lastSeenAt: string;
  firstSeenOffsetMs: number;
  middleSeenOffsetMs: number;
  lastSeenOffsetMs: number;
  firstSeenOffsetLabel: string;
  middleSeenOffsetLabel: string;
  lastSeenOffsetLabel: string;
  frameCount: number;
  sampleFps: number;
  maxConfidence: number;
  avgConfidence: number;
  embeddingStatus: string;
  embeddingModel?: string | null;
  faceStatus: string;
  faceModel?: string | null;
  closedReason: string;
  firstCropDataUrl: string;
  middleCropDataUrl: string;
  lastCropDataUrl: string;
}

export interface RealtimeAlertEvent {
  type: "alert.created";
  payload: AlertEvent;
}

export interface RealtimeHealthEvent {
  type: "camera.health_changed";
  payload: { cameraId: string; health: HealthStatus; happenedAt: string };
}

export type RealtimeEvent = RealtimeAlertEvent | RealtimeHealthEvent;

export interface VmsApiClient {
  listSites(): Promise<Site[]>;
  listCameras(siteId?: string): Promise<Camera[]>;
  createCamera(input: CreateCameraInput): Promise<Camera>;
  reconnectCamera(cameraId: string): Promise<Camera>;
  deleteCamera(cameraId: string): Promise<void>;
  listLiveTiles(siteId?: string): Promise<LiveStreamTile[]>;
  getOverview(siteId?: string): Promise<OverviewSnapshot>;
  listAlerts(filter?: AlertFilter): Promise<AlertEvent[]>;
  listIncidents(): Promise<Incident[]>;
  getIncidentById(id: string): Promise<Incident | undefined>;
  searchPlayback(params: PlaybackSearchParams): Promise<PlaybackSegment[]>;
  listDevices(siteId?: string): Promise<Device[]>;
  listVisionSources(): Promise<VisionSource[]>;
  getVisionStatus(): Promise<VisionPipelineStatus>;
  runVisionMockJob(sourceIds?: string[]): Promise<VisionJobStatus>;
  listCropTracks(filter?: CropTrackFilter): Promise<CropTrack[]>;
}
