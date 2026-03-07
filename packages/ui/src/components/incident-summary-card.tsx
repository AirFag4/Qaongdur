import type { Incident } from "@qaongdur/types";
import { Badge } from "./ui/badge";
import { Card } from "./ui/card";

const severityTone = {
  low: "stone",
  medium: "amber",
  high: "amber",
  critical: "red",
} as const;

export function IncidentSummaryCard({
  incident,
  onOpen,
}: {
  incident: Incident;
  onOpen?: (incidentId: string) => void;
}) {
  return (
    <Card className="space-y-2">
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="text-sm font-semibold text-stone-100">{incident.title}</p>
          <p className="mt-1 font-mono text-[11px] text-stone-500">{incident.id}</p>
        </div>
        <Badge tone={severityTone[incident.severity]}>{incident.severity}</Badge>
      </div>
      <p className="text-xs text-stone-400">{incident.summary}</p>
      <div className="flex items-center justify-between gap-2 pt-1 text-xs text-stone-500">
        <p>Owner: {incident.owner}</p>
        <p>{incident.cameraIds.length} cameras</p>
      </div>
      {onOpen ? (
        <button
          type="button"
          onClick={() => onOpen(incident.id)}
          className="text-xs font-semibold text-cyan-300 hover:text-cyan-200"
        >
          Open incident
        </button>
      ) : null}
    </Card>
  );
}
