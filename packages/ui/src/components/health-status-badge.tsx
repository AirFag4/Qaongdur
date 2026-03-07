import type { HealthStatus } from "@qaongdur/types";
import { Badge } from "./ui/badge";

const statusTone: Record<HealthStatus, "emerald" | "amber" | "red" | "stone"> = {
  healthy: "emerald",
  warning: "amber",
  critical: "red",
  offline: "stone",
};

export function HealthStatusBadge({ status }: { status: HealthStatus }) {
  return (
    <Badge tone={statusTone[status]} className="gap-1.5">
      <span className="h-1.5 w-1.5 rounded-full bg-current" />
      {status}
    </Badge>
  );
}
