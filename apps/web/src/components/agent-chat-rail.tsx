import type { RealtimeEvent } from "@qaongdur/types";
import { Card, CardDescription, CardTitle } from "@qaongdur/ui";
import { Button } from "@qaongdur/ui";

export function AgentChatRail({ recentEvents }: { recentEvents: RealtimeEvent[] }) {
  return (
    <div className="flex h-full flex-col gap-3">
      <Card className="space-y-2">
        <div className="flex items-center justify-between">
          <CardTitle>Agent Assistant</CardTitle>
          <span className="rounded-full border border-cyan-800 bg-cyan-950/60 px-2 py-1 text-[10px] uppercase tracking-wide text-cyan-200">
            Reserved
          </span>
        </div>
        <CardDescription>
          This panel is reserved for in-app incident chat and tool approvals.
        </CardDescription>
        <div className="space-y-2 rounded-md border border-stone-700 bg-stone-950/60 p-2 text-xs text-stone-400">
          <p>Suggested prompts:</p>
          <p className="rounded border border-stone-700 bg-stone-900 px-2 py-1">
            "Summarize critical alerts from the last 2 hours"
          </p>
          <p className="rounded border border-stone-700 bg-stone-900 px-2 py-1">
            "Generate incident handover report for shift B"
          </p>
        </div>
        <Button variant="secondary" size="sm" className="w-full">
          Open Agent (coming soon)
        </Button>
      </Card>

      <Card className="flex-1 space-y-2 overflow-hidden">
        <div className="flex items-center justify-between">
          <CardTitle>Realtime Feed</CardTitle>
          <CardDescription>Mock websocket events</CardDescription>
        </div>
        <div className="max-h-[48vh] space-y-2 overflow-auto pr-1">
          {recentEvents.length ? (
            recentEvents.map((event, index) => (
              <div key={`${event.type}-${index}`} className="rounded border border-stone-700 bg-stone-950/70 p-2">
                <p className="text-[11px] uppercase tracking-wide text-stone-500">{event.type}</p>
                <p className="mt-1 text-xs text-stone-300">
                  {event.type === "alert.created"
                    ? `${event.payload.title} (${event.payload.severity})`
                    : `${event.payload.cameraId} -> ${event.payload.health}`}
                </p>
              </div>
            ))
          ) : (
            <p className="text-xs text-stone-500">Waiting for events...</p>
          )}
        </div>
      </Card>
    </div>
  );
}
