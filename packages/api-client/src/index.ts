import type { VmsApiClient } from "@qaongdur/types";
import { canFallbackToMock, HttpApiClient, type HttpApiClientConfig } from "./http-api-client";
import { mockApiClient } from "./mock-api-client";
import { MockRealtimeEventSocket } from "./mock-event-socket";

export * from "./mock-event-socket";
export * from "./http-api-client";

const withFallback = <T>(
  backend: () => Promise<T>,
  fallback: () => Promise<T>,
) => async () => {
  try {
    return await backend();
  } catch (error) {
    if (canFallbackToMock(error)) {
      return fallback();
    }
    throw error;
  }
};

export const createApiClient = (config?: HttpApiClientConfig): VmsApiClient => {
  if (!config?.baseUrl || !config.getAccessToken) {
    return mockApiClient;
  }

  const httpClient = new HttpApiClient({
    baseUrl: config.baseUrl,
    getAccessToken: config.getAccessToken,
  });

  return {
    listSites: withFallback(() => httpClient.listSites(), () => mockApiClient.listSites()),
    listCameras: (siteId) =>
      withFallback(
        () => httpClient.listCameras(siteId),
        () => mockApiClient.listCameras(siteId),
      )(),
    createCamera: (input) => httpClient.createCamera(input),
    reconnectCamera: (cameraId) => httpClient.reconnectCamera(cameraId),
    deleteCamera: (cameraId) => httpClient.deleteCamera(cameraId),
    listLiveTiles: (siteId) =>
      withFallback(
        () => httpClient.listLiveTiles(siteId),
        () => mockApiClient.listLiveTiles(siteId),
      )(),
    getOverview: (siteId) =>
      withFallback(
        () => httpClient.getOverview(siteId),
        () => mockApiClient.getOverview(siteId),
      )(),
    listAlerts: (filter) =>
      withFallback(
        () => httpClient.listAlerts(filter),
        () => mockApiClient.listAlerts(filter),
      )(),
    listIncidents: () =>
      withFallback(() => httpClient.listIncidents(), () => mockApiClient.listIncidents())(),
    getIncidentById: (id) =>
      withFallback(
        () => httpClient.getIncidentById(id),
        () => mockApiClient.getIncidentById(id),
      )(),
    searchPlayback: (params) =>
      withFallback(
        () => httpClient.searchPlayback(params),
        () => mockApiClient.searchPlayback(params),
      )(),
    listDevices: (siteId) =>
      withFallback(
        () => httpClient.listDevices(siteId),
        () => mockApiClient.listDevices(siteId),
      )(),
    listVisionSources: () =>
      withFallback(
        () => httpClient.listVisionSources(),
        () => mockApiClient.listVisionSources(),
      )(),
    getVisionStatus: () =>
      withFallback(
        () => httpClient.getVisionStatus(),
        () => mockApiClient.getVisionStatus(),
      )(),
    runVisionMockJob: (sourceIds) => httpClient.runVisionMockJob(sourceIds),
    listCropTracks: (filter) =>
      withFallback(
        () => httpClient.listCropTracks(filter),
        () => mockApiClient.listCropTracks(filter),
      )(),
    getCropTrack: (trackId) =>
      withFallback(
        () => httpClient.getCropTrack(trackId),
        () => mockApiClient.getCropTrack(trackId),
      )(),
    getSystemSettings: () =>
      withFallback(
        () => httpClient.getSystemSettings(),
        () => mockApiClient.getSystemSettings(),
      )(),
  };
};

export const createRealtimeSocket = () => new MockRealtimeEventSocket();
