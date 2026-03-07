import { useMemo, useState } from "react";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { useQuery } from "@tanstack/react-query";
import { Button, Card, CardDescription, CardTitle, EmptyState, FilterBar, FilterField, LoadingState } from "@qaongdur/ui";
import type { PlaybackSearchParams } from "@qaongdur/types";
import { apiClient, queryKeys } from "../lib/api";
import { useOperatorOutlet } from "../app/use-operator-outlet";

const toInputValue = (date: Date) => date.toISOString().slice(0, 16);

const playbackSchema = z
  .object({
    from: z.string().min(1),
    to: z.string().min(1),
    includeAlerts: z.boolean(),
  })
  .refine((values) => new Date(values.from).getTime() < new Date(values.to).getTime(), {
    message: "`from` must be earlier than `to`",
    path: ["to"],
  });

type PlaybackForm = z.infer<typeof playbackSchema>;

export function PlaybackSearchPage() {
  const { cameras, selectedCameraIds } = useOperatorOutlet();
  const [initialWindow] = useState(() => {
    const now = Date.now();
    return {
      from: toInputValue(new Date(now - 2 * 60 * 60 * 1000)),
      to: toInputValue(new Date(now)),
    };
  });
  const [activeParams, setActiveParams] = useState<PlaybackSearchParams | null>(null);

  const form = useForm<PlaybackForm>({
    resolver: zodResolver(playbackSchema),
    defaultValues: {
      from: initialWindow.from,
      to: initialWindow.to,
      includeAlerts: true,
    },
  });

  const playback = useQuery({
    queryKey: queryKeys.playback(JSON.stringify(activeParams ?? {})),
    queryFn: () => (activeParams ? apiClient.searchPlayback(activeParams) : Promise.resolve([])),
    enabled: Boolean(activeParams),
  });

  const cameraNameById = useMemo(
    () => new Map(cameras.map((camera) => [camera.id, camera.name])),
    [cameras],
  );

  return (
    <div className="space-y-3">
      <FilterBar>
        <FilterField label="From">
          <input type="datetime-local" className="form-input" {...form.register("from")} />
        </FilterField>
        <FilterField label="To">
          <input type="datetime-local" className="form-input" {...form.register("to")} />
        </FilterField>
        <label className="mt-4 flex items-center gap-2 text-xs text-stone-300">
          <input type="checkbox" {...form.register("includeAlerts")} />
          Include alert-heavy segments
        </label>
        <Button
          size="sm"
          variant="secondary"
          onClick={form.handleSubmit((values) =>
            setActiveParams({
              cameraIds: selectedCameraIds,
              from: new Date(values.from).toISOString(),
              to: new Date(values.to).toISOString(),
              includeAlerts: values.includeAlerts,
            }),
          )}
        >
          Search Playback
        </Button>
      </FilterBar>

      <Card className="space-y-3">
        <div className="flex items-center justify-between">
          <CardTitle>Timeline Results</CardTitle>
          <CardDescription>15-minute segment buckets</CardDescription>
        </div>
        {!activeParams ? (
          <EmptyState
            title="Run a playback search"
            description="Select a time range to render a timeline view."
          />
        ) : playback.isLoading ? (
          <LoadingState label="Searching playback indexes..." />
        ) : !playback.data?.length ? (
          <EmptyState
            title="No timeline segments"
            description="No segments matched this request."
          />
        ) : (
          <div className="space-y-2">
            {playback.data.map((segment) => (
              <div
                key={segment.id}
                className="rounded-md border border-stone-700 bg-stone-950/60 p-2"
              >
                <div className="flex items-center justify-between gap-2">
                  <p className="text-xs font-medium text-stone-100">
                    {cameraNameById.get(segment.cameraId) ?? segment.cameraId}
                  </p>
                  <p className="font-mono text-[11px] text-stone-500">
                    {new Date(segment.startAt).toLocaleTimeString()} -{" "}
                    {new Date(segment.endAt).toLocaleTimeString()}
                  </p>
                </div>
                <div className="mt-2 h-2 w-full rounded bg-stone-800">
                  <div
                    className="h-full rounded bg-cyan-400"
                    style={{ width: `${Math.max(segment.motionScore * 100, 4)}%` }}
                  />
                </div>
                <p className="mt-1 text-[11px] text-stone-400">
                  Motion score: {segment.motionScore} • Alerts: {segment.alerts}
                </p>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}
