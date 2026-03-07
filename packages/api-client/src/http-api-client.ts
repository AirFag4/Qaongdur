import type {
  AlertEvent,
  AlertFilter,
  Camera,
  CreateCameraInput,
  Device,
  Incident,
  LiveStreamTile,
  OverviewSnapshot,
  PlaybackSearchParams,
  PlaybackSegment,
  Site,
  VmsApiClient,
} from "@qaongdur/types";


export interface HttpApiClientConfig {
  baseUrl?: string;
  getAccessToken?: () => string | undefined;
}


class HttpApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}


const appendSearch = (path: string, params: Record<string, string | undefined>) => {
  const url = new URL(path, "http://qaongdur.local");
  Object.entries(params).forEach(([key, value]) => {
    if (value) {
      url.searchParams.set(key, value);
    }
  });
  return `${url.pathname}${url.search}`;
};


const isNetworkError = (error: unknown) =>
  error instanceof TypeError || error instanceof DOMException;


export class HttpApiClient implements VmsApiClient {
  private readonly config: Required<HttpApiClientConfig>;

  constructor(config: Required<HttpApiClientConfig>) {
    this.config = config;
  }

  async listSites(): Promise<Site[]> {
    return this._request("/api/v1/sites");
  }

  async listCameras(siteId?: string): Promise<Camera[]> {
    return this._request(appendSearch("/api/v1/cameras", { siteId }));
  }

  async createCamera(input: CreateCameraInput): Promise<Camera> {
    return this._request("/api/v1/cameras", {
      method: "POST",
      body: JSON.stringify(input),
    });
  }

  async listLiveTiles(siteId?: string): Promise<LiveStreamTile[]> {
    return this._request(appendSearch("/api/v1/live-tiles", { siteId }));
  }

  async getOverview(siteId?: string): Promise<OverviewSnapshot> {
    return this._request(appendSearch("/api/v1/overview", { siteId }));
  }

  async listAlerts(filter?: AlertFilter): Promise<AlertEvent[]> {
    return this._request(
      appendSearch("/api/v1/alerts", {
        siteId: filter?.siteId,
        cameraId: filter?.cameraId,
        severity: filter?.severity && filter.severity !== "all" ? filter.severity : undefined,
        status: filter?.status && filter.status !== "all" ? filter.status : undefined,
        search: filter?.search,
      }),
    );
  }

  async listIncidents(): Promise<Incident[]> {
    return this._request("/api/v1/incidents");
  }

  async getIncidentById(id: string): Promise<Incident | undefined> {
    try {
      return await this._request(`/api/v1/incidents/${id}`);
    } catch (error) {
      if (error instanceof HttpApiError && error.status === 404) {
        return undefined;
      }
      throw error;
    }
  }

  async searchPlayback(params: PlaybackSearchParams): Promise<PlaybackSegment[]> {
    return this._request("/api/v1/playback/search", {
      method: "POST",
      body: JSON.stringify(params),
    });
  }

  async listDevices(siteId?: string): Promise<Device[]> {
    return this._request(appendSearch("/api/v1/devices", { siteId }));
  }

  async _request<T>(path: string, init?: RequestInit): Promise<T> {
    const response = await fetch(`${this.config.baseUrl}${path}`, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${this.config.getAccessToken() ?? ""}`,
        ...(init?.headers ?? {}),
      },
    });

    if (!response.ok) {
      throw new HttpApiError(
        response.status,
        (await response.text()) || `Request failed with ${response.status}.`,
      );
    }

    return (await response.json()) as T;
  }
}


export const canFallbackToMock = (error: unknown) => isNetworkError(error);
