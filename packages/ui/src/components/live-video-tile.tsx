import { useEffect, useRef, useState } from "react";
import Hls from "hls.js";
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
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const [streamError, setStreamError] = useState<string | null>(null);

  useEffect(() => {
    const video = videoRef.current;
    if (!video) {
      return;
    }

    setStreamError(null);

    if (!tile.hlsUrl) {
      video.pause();
      video.removeAttribute("src");
      video.load();
      return;
    }

    if (video.canPlayType("application/vnd.apple.mpegurl")) {
      video.src = tile.hlsUrl;
      void video.play().catch(() => undefined);
      return () => {
        video.pause();
        video.removeAttribute("src");
        video.load();
      };
    }

    if (!Hls.isSupported()) {
      setStreamError("This browser cannot play HLS live streams.");
      return;
    }

    const hls = new Hls({
      enableWorker: true,
      lowLatencyMode: true,
    });
    hls.loadSource(tile.hlsUrl);
    hls.attachMedia(video);
    hls.on(Hls.Events.MANIFEST_PARSED, () => {
      void video.play().catch(() => undefined);
    });
    hls.on(Hls.Events.ERROR, (_, data) => {
      if (data.fatal) {
        setStreamError("Unable to load the live stream.");
      }
    });

    return () => {
      hls.destroy();
      video.pause();
      video.removeAttribute("src");
      video.load();
    };
  }, [tile.hlsUrl]);

  return (
    <div className="group relative overflow-hidden rounded-xl border border-stone-700 bg-stone-900">
      <div
        className={cn(
          "relative w-full bg-[radial-gradient(circle_at_24%_16%,rgba(34,211,238,0.15),transparent_42%),radial-gradient(circle_at_75%_84%,rgba(251,191,36,0.08),transparent_52%),linear-gradient(120deg,#151312,#1a1817_35%,#11100f)]",
          compact ? "aspect-video" : "aspect-[16/10]",
        )}
      >
        {tile.hlsUrl ? (
          <video
            ref={videoRef}
            className="absolute inset-0 h-full w-full object-cover"
            autoPlay
            muted
            playsInline
          />
        ) : null}
        <div className="pointer-events-none absolute inset-0 bg-[linear-gradient(to_bottom,transparent_72%,rgba(8,8,8,0.72))]" />
        <div className="pointer-events-none absolute inset-0 bg-[linear-gradient(to_right,rgba(0,0,0,0.18)_1px,transparent_1px),linear-gradient(to_bottom,rgba(0,0,0,0.18)_1px,transparent_1px)] bg-[size:24px_24px] opacity-35" />

        {!tile.hlsUrl ? (
          <div className="absolute inset-0 flex items-center justify-center">
            <p className="rounded-full border border-stone-700 bg-stone-950/85 px-3 py-1 text-[11px] font-medium text-stone-300">
              Awaiting live stream
            </p>
          </div>
        ) : null}

        {streamError ? (
          <div className="absolute left-2 top-2 rounded-md border border-amber-500/40 bg-amber-950/85 px-2 py-1 text-[11px] text-amber-200">
            {streamError}
          </div>
        ) : null}

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
