import { useMutation } from "@tanstack/react-query";
import { Badge } from "@qaongdur/ui";
import type { RealtimeEvent } from "@qaongdur/types";
import { Card, CardDescription, CardTitle } from "@qaongdur/ui";
import { Button } from "@qaongdur/ui";
import { RoleGate } from "../auth/role-gate";
import { useAuth } from "../auth/use-auth";
import {
  requestDestructivePurge,
  requestEvidenceExport,
} from "../lib/control-api";

export function AgentChatRail({
  recentEvents,
  realtimeMode,
}: {
  recentEvents: RealtimeEvent[];
  realtimeMode: "mock" | "disabled";
}) {
  const auth = useAuth();
  const accessToken = auth.session?.accessToken;
  const exportMutation = useMutation({
    mutationFn: () => requestEvidenceExport(accessToken!),
  });

  const purgeMutation = useMutation({
    mutationFn: () => requestDestructivePurge(accessToken!),
  });

  return (
    <div className="flex h-full flex-col gap-3">
      <Card className="space-y-2">
        <div className="flex items-center justify-between">
          <CardTitle>Agent Assistant</CardTitle>
          <Badge tone="cyan">Reserved</Badge>
        </div>
        <CardDescription>
          This panel stays focused on agent and realtime tools. Auth controls were moved to Settings.
        </CardDescription>
        <div className="theme-panel-muted space-y-2 p-2 text-xs">
          <p>Suggested prompts:</p>
          <p className="theme-panel-subtle px-2 py-1">
            "Summarize critical alerts from the last 2 hours"
          </p>
          <p className="theme-panel-subtle px-2 py-1">
            "Generate incident handover report for shift B"
          </p>
        </div>
        <Button variant="secondary" size="sm" className="w-full">
          Open Agent (coming soon)
        </Button>
        <RoleGate
          anyOf={["operator", "reviewer", "site-admin", "platform-admin"]}
          fallback={
            <p className="theme-panel-muted theme-panel-caption p-2 text-xs">
              Operator, reviewer, or admin roles are required to approve evidence exports.
            </p>
          }
        >
          <Button
            size="sm"
            variant="ghost"
            className="w-full"
            onClick={() => exportMutation.mutate()}
            disabled={exportMutation.isPending}
          >
            {exportMutation.isPending ? "Submitting Export Approval..." : "Run Approval Demo"}
          </Button>
        </RoleGate>
        {exportMutation.error ? (
          <p className="text-xs text-red-300">
            {exportMutation.error instanceof Error
              ? exportMutation.error.message
              : "Approval request failed."}
          </p>
        ) : null}
        {exportMutation.data ? (
          <p className="text-xs text-emerald-300">
            Approval recorded via backend for {exportMutation.data.action}.
          </p>
        ) : null}
        <RoleGate
          anyOf={["platform-admin"]}
          fallback={
            <p className="theme-panel-muted theme-panel-caption p-2 text-xs">
              Destructive actions are platform-admin only and require step-up authentication.
            </p>
          }
        >
          <Button
            size="sm"
            variant="attention"
            className="w-full"
            onClick={() => purgeMutation.mutate()}
            disabled={purgeMutation.isPending}
          >
            {purgeMutation.isPending ? "Checking Step-Up..." : "Run Destructive Demo"}
          </Button>
        </RoleGate>
        {purgeMutation.error ? (
          <p className="text-xs text-amber-300">
            {purgeMutation.error instanceof Error
              ? purgeMutation.error.message
              : "Destructive action failed."}
          </p>
        ) : null}
        {purgeMutation.data ? (
          <p className="text-xs text-emerald-300">
            Step-up action accepted by backend for {purgeMutation.data.action}.
          </p>
        ) : null}
      </Card>

      <Card className="flex-1 space-y-2 overflow-hidden">
        <div className="flex items-center justify-between">
          <CardTitle>Realtime Feed</CardTitle>
          <CardDescription>
            {realtimeMode === "mock" ? "Mock websocket events" : "Realtime websocket not wired yet"}
          </CardDescription>
        </div>
        <div className="max-h-[48vh] space-y-2 overflow-auto pr-1">
          {recentEvents.length ? (
            recentEvents.map((event, index) => (
              <div key={`${event.type}-${index}`} className="theme-panel-muted p-2">
                <p className="theme-panel-caption text-[11px] uppercase tracking-wide">{event.type}</p>
                <p className="mt-1 text-xs text-[var(--qa-panel-text)]">
                  {event.type === "alert.created"
                    ? `${event.payload.title} (${event.payload.severity})`
                    : `${event.payload.cameraId} -> ${event.payload.health}`}
                </p>
              </div>
            ))
          ) : (
            <p className="theme-panel-caption text-xs">
              {realtimeMode === "mock"
                ? "Waiting for events..."
                : "Realtime feed is disabled until backend event streaming is wired."}
            </p>
          )}
        </div>
      </Card>
    </div>
  );
}
