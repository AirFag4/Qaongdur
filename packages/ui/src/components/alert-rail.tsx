import type { AlertEvent } from "@qaongdur/types";
import { Badge } from "./ui/badge";
import { Card, CardDescription, CardTitle } from "./ui/card";

const toneBySeverity = {
  low: "stone",
  medium: "amber",
  high: "amber",
  critical: "red",
} as const;

export function AlertRail({
  alerts,
  onSelect,
}: {
  alerts: AlertEvent[];
  onSelect?: (alertId: string) => void;
}) {
  return (
    <Card className="space-y-3">
      <div className="flex items-center justify-between">
        <CardTitle>Alert Rail</CardTitle>
        <CardDescription>Newest first</CardDescription>
      </div>
      <div className="max-h-96 space-y-2 overflow-auto pr-1">
        {alerts.slice(0, 10).map((alert) => (
          <button
            key={alert.id}
            type="button"
            onClick={() => onSelect?.(alert.id)}
            className="w-full rounded-lg border border-stone-700 bg-stone-950/70 p-2 text-left transition-colors hover:border-cyan-700"
          >
            <div className="flex items-center justify-between gap-2">
              <p className="truncate text-sm font-medium text-stone-100">{alert.title}</p>
              <Badge tone={toneBySeverity[alert.severity]}>{alert.severity}</Badge>
            </div>
            <p className="mt-1 text-xs text-stone-400">{alert.summary}</p>
            <p className="mt-2 font-mono text-[11px] text-stone-500">
              {new Date(alert.happenedAt).toLocaleString()}
            </p>
          </button>
        ))}
      </div>
    </Card>
  );
}
