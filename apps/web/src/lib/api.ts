import { createApiClient, createRealtimeSocket } from "@qaongdur/api-client";

export const apiClient = createApiClient();
export const realtimeSocket = createRealtimeSocket();

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
};
