import { createApiClient, createRealtimeSocket } from "@qaongdur/api-client";
import { getControlApiBaseUrl, getKeycloakClient } from "../auth/keycloak";

const getAccessToken = () => {
  try {
    return getKeycloakClient().token ?? undefined;
  } catch {
    return undefined;
  }
};

export const apiClient = createApiClient({
  baseUrl: getControlApiBaseUrl(),
  getAccessToken,
});
export const realtimeSocket = createRealtimeSocket({
  baseUrl: getControlApiBaseUrl(),
  getAccessToken,
});

export const queryKeys = {
  sites: ["sites"] as const,
  cameras: (siteId?: string) => ["cameras", siteId ?? "all"] as const,
  liveTiles: (siteId?: string) => ["live-tiles", siteId ?? "all"] as const,
  overview: (siteId?: string) => ["overview", siteId ?? "all"] as const,
  alerts: (filters?: Record<string, unknown>) =>
    ["alerts", JSON.stringify(filters ?? {})] as const,
  incidents: ["incidents"] as const,
  incident: (id: string) => ["incident", id] as const,
  playback: (hash: string) => ["playback", hash] as const,
  devices: (siteId?: string) => ["devices", siteId ?? "all"] as const,
  visionSources: ["vision-sources"] as const,
  visionStatus: ["vision-status"] as const,
  cropTracks: (hash: string) => ["crop-tracks", hash] as const,
  cropTrack: (id: string) => ["crop-track", id] as const,
  systemSettings: ["system-settings"] as const,
};
