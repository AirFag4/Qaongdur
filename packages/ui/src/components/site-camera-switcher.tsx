import type { Camera, Site } from "@qaongdur/types";
import { Button } from "./ui/button";

export interface SiteCameraSwitcherProps {
  sites: Site[];
  cameras: Camera[];
  siteId?: string;
  selectedCameraIds: string[];
  onSiteChange: (siteId: string | undefined) => void;
  onCameraToggle: (cameraId: string) => void;
}

export function SiteCameraSwitcher({
  sites,
  cameras,
  siteId,
  selectedCameraIds,
  onSiteChange,
  onCameraToggle,
}: SiteCameraSwitcherProps) {
  return (
    <div className="flex flex-col gap-3 rounded-lg border border-stone-700 bg-stone-900/80 p-3">
      <div className="flex items-center justify-between">
        <p className="text-xs font-semibold uppercase tracking-wide text-stone-400">
          Site Context
        </p>
        <Button
          size="sm"
          variant="ghost"
          onClick={() => onSiteChange(undefined)}
          className="h-6 px-2"
        >
          All Sites
        </Button>
      </div>
      <select
        className="h-9 rounded-md border border-stone-700 bg-stone-950 px-2 text-sm text-stone-100 outline-none focus:border-cyan-700"
        value={siteId ?? ""}
        onChange={(event) => onSiteChange(event.target.value || undefined)}
      >
        <option value="">All sites</option>
        {sites.map((site) => (
          <option key={site.id} value={site.id}>
            {site.code} • {site.name}
          </option>
        ))}
      </select>
      <div className="flex flex-wrap gap-2">
        {cameras.slice(0, 8).map((camera) => {
          const selected = selectedCameraIds.includes(camera.id);
          return (
            <Button
              key={camera.id}
              size="sm"
              variant={selected ? "default" : "ghost"}
              onClick={() => onCameraToggle(camera.id)}
              className="h-7 px-2 text-[11px]"
            >
              {camera.name}
            </Button>
          );
        })}
      </div>
    </div>
  );
}
