import type { Camera, RealtimeEvent, Site } from "@qaongdur/types";
import type { CameraGridSize } from "@qaongdur/ui";

export interface OperatorOutletContext {
  sites: Site[];
  cameras: Camera[];
  siteId?: string;
  selectedCameraIds: string[];
  liveGridSize: CameraGridSize;
  recentEvents: RealtimeEvent[];
  themeMode: "polarized-dark" | "polarized-light";
  setSiteId: (siteId: string | undefined) => void;
  setSelectedCameraIds: (cameraIds: string[]) => void;
  toggleCameraSelection: (cameraId: string) => void;
  setLiveGridSize: (size: CameraGridSize) => void;
  openCommandPalette: () => void;
}
