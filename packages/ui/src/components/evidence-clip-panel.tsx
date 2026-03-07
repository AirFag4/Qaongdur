import type { EvidenceClip } from "@qaongdur/types";
import { Card, CardDescription, CardTitle } from "./ui/card";
import { Badge } from "./ui/badge";

export function EvidenceClipPanel({
  clips,
  onSelectClip,
}: {
  clips: EvidenceClip[];
  onSelectClip?: (clipId: string) => void;
}) {
  return (
    <Card className="space-y-3">
      <div className="flex items-center justify-between">
        <CardTitle>Evidence Clips</CardTitle>
        <CardDescription>{clips.length} attached</CardDescription>
      </div>
      <div className="space-y-2">
        {clips.map((clip) => (
          <button
            key={clip.id}
            type="button"
            onClick={() => onSelectClip?.(clip.id)}
            className="w-full rounded-lg border border-stone-700 bg-stone-950/70 p-2 text-left transition-colors hover:border-cyan-700"
          >
            <div className="flex items-center justify-between gap-2">
              <p className="truncate text-sm text-stone-100">{clip.title}</p>
              <Badge tone={clip.type === "video" ? "cyan" : "stone"}>{clip.type}</Badge>
            </div>
            <p className="mt-1 font-mono text-[11px] text-stone-500">
              {new Date(clip.startAt).toLocaleString()} - {new Date(clip.endAt).toLocaleTimeString()}
            </p>
            <p className="mt-1 text-xs text-stone-400">{clip.storageRef}</p>
          </button>
        ))}
      </div>
    </Card>
  );
}
