import type { Camera, LiveStreamTile } from "@qaongdur/types";
import { Badge } from "./ui/badge";
import { HealthStatusBadge } from "./health-status-badge";
import { cn } from "../lib/utils";

const severityTone = {
  low: "stone",
  medium: "amber",
  high: "amber",
  critical: "red",
} as const;

export function LiveVideoTile({
  camera,
  tile,
  compact = false,
}: {
  camera: Camera;
  tile: LiveStreamTile;
  compact?: boolean;
}) {
  return (
    <div className="group relative overflow-hidden rounded-xl border border-stone-700 bg-stone-900">
      <div
        className={cn(
          "relative w-full bg-[radial-gradient(circle_at_24%_16%,rgba(34,211,238,0.15),transparent_42%),radial-gradient(circle_at_75%_84%,rgba(251,191,36,0.08),transparent_52%),linear-gradient(120deg,#151312,#1a1817_35%,#11100f)]",
          compact ? "aspect-video" : "aspect-[16/10]",
        )}
      >
        <div className="pointer-events-none absolute inset-0 bg-[linear-gradient(to_bottom,transparent_72%,rgba(8,8,8,0.72))]" />
        <div className="pointer-events-none absolute inset-0 bg-[linear-gradient(to_right,rgba(0,0,0,0.18)_1px,transparent_1px),linear-gradient(to_bottom,rgba(0,0,0,0.18)_1px,transparent_1px)] bg-[size:24px_24px] opacity-35" />

        {tile.detections.map((box) => (
          <div
            key={box.id}
            className="absolute border border-cyan-300/80 bg-cyan-400/10"
            style={{
              left: `${box.x}%`,
              top: `${box.y}%`,
              width: `${box.width}%`,
              height: `${box.height}%`,
            }}
          >
            <span className="absolute -top-5 left-0 rounded bg-black/80 px-1 py-0.5 text-[10px] text-cyan-200">
              {box.label} {Math.round(box.confidence * 100)}%
            </span>
          </div>
        ))}

        <div className="absolute bottom-2 left-2 right-2 flex items-end justify-between gap-2">
          <div>
            <p className="font-medium text-stone-100">{camera.name}</p>
            <p className="font-mono text-[11px] text-stone-300">
              {camera.zone} • {camera.resolution} • {camera.fps} FPS
            </p>
          </div>
          <div className="space-y-1 text-right">
            <p className="font-mono text-[11px] text-cyan-300">
              {tile.isLive ? `${tile.latencyMs}ms` : "offline"}
            </p>
            <p className="font-mono text-[11px] text-stone-400">{tile.bitrateKbps} kbps</p>
          </div>
        </div>
      </div>
      <div className="flex items-center justify-between gap-2 border-t border-stone-700 px-3 py-2">
        <HealthStatusBadge status={camera.health} />
        <div className="flex items-center gap-1.5">
          {tile.detections.slice(0, 2).map((detection) => (
            <Badge
              key={detection.id}
              tone={severityTone[detection.severity]}
              className="text-[10px]"
            >
              {detection.label}
            </Badge>
          ))}
        </div>
      </div>
    </div>
  );
}
