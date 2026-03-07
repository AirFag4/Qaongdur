import type { Camera, LiveStreamTile } from "@qaongdur/types";
import { EmptyState } from "./empty-state";
import { LiveVideoTile } from "./live-video-tile";
import { cn } from "../lib/utils";

export type CameraGridSize = 1 | 4 | 9 | 16;

const gridClassBySize: Record<CameraGridSize, string> = {
  1: "grid-cols-1",
  4: "grid-cols-1 md:grid-cols-2",
  9: "grid-cols-1 md:grid-cols-2 xl:grid-cols-3",
  16: "grid-cols-1 md:grid-cols-2 xl:grid-cols-4",
};

export function CameraGrid({
  cameras,
  tiles,
  gridSize,
}: {
  cameras: Camera[];
  tiles: LiveStreamTile[];
  gridSize: CameraGridSize;
}) {
  if (!cameras.length) {
    return (
      <EmptyState
        title="No cameras selected"
        description="Pick one or more cameras to load live streams."
      />
    );
  }

  const tileByCameraId = new Map(tiles.map((tile) => [tile.cameraId, tile]));
  const visibleCameras = cameras.slice(0, gridSize);

  return (
    <div className={cn("grid gap-3", gridClassBySize[gridSize])}>
      {visibleCameras.map((camera) => {
        const tile = tileByCameraId.get(camera.id);
        if (!tile) {
          return (
            <div
              key={camera.id}
              className="aspect-video rounded-xl border border-dashed border-stone-700 bg-stone-900/40"
            />
          );
        }
        return <LiveVideoTile key={camera.id} camera={camera} tile={tile} compact />;
      })}
    </div>
  );
}
