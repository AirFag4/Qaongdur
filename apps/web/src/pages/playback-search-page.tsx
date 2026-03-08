import { useEffect, useMemo, useState } from "react";
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
  const [selectedSegmentId, setSelectedSegmentId] = useState<string>();

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
  const selectedSegment =
    playback.data?.find((segment) => segment.id === selectedSegmentId) ?? playback.data?.[0];

  useEffect(() => {
    if (!playback.data?.length) {
      setSelectedSegmentId(undefined);
      return;
    }

    setSelectedSegmentId((current) =>
      current && playback.data.some((segment) => segment.id === current)
        ? current
        : playback.data[0].id,
    );
  }, [playback.data]);

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
          <CardDescription>Recorded spans returned by MediaMTX playback</CardDescription>
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
          <div className="grid gap-3 xl:grid-cols-[minmax(0,1fr)_minmax(360px,460px)]">
            <div className="space-y-2">
              {playback.data.map((segment) => (
                <button
                  key={segment.id}
                  type="button"
                  onClick={() => setSelectedSegmentId(segment.id)}
                  className={`w-full rounded-md border p-2 text-left transition-colors ${
                    selectedSegment?.id === segment.id
                      ? "border-cyan-700 bg-cyan-950/30"
                      : "border-stone-700 bg-stone-950/60 hover:border-stone-600"
                  }`}
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
                    Duration: {Math.round(segment.durationSec ?? 0)}s • Alerts: {segment.alerts}
                  </p>
                </button>
              ))}
            </div>

            <Card className="space-y-3">
              <div>
                <CardTitle>Playback Viewer</CardTitle>
                <CardDescription>
                  {selectedSegment
                    ? `${cameraNameById.get(selectedSegment.cameraId) ?? selectedSegment.cameraId} • ${new Date(selectedSegment.startAt).toLocaleString()}`
                    : "Select a recorded span to start playback."}
                </CardDescription>
              </div>

              {selectedSegment?.playbackUrl ? (
                <div className="space-y-3">
                  <video
                    key={selectedSegment.playbackUrl}
                    className="aspect-video w-full rounded-lg border border-stone-700 bg-black"
                    controls
                    preload="metadata"
                  >
                    <source src={selectedSegment.playbackUrl} type="video/mp4" />
                  </video>
                  {selectedSegment.downloadUrl ? (
                    <div className="flex justify-end">
                      <a
                        href={selectedSegment.downloadUrl}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-flex rounded-md border border-stone-700 px-3 py-2 text-sm text-stone-200 transition-colors hover:border-stone-500 hover:bg-stone-900"
                      >
                        Download MP4
                      </a>
                    </div>
                  ) : null}
                </div>
              ) : (
                <div className="flex aspect-video items-center justify-center rounded-lg border border-dashed border-stone-700 bg-stone-950/60 px-4 text-center text-sm text-stone-400">
                  Playback video is only available when the real backend returns MediaMTX recording URLs.
                </div>
              )}
            </Card>
          </div>
        )}
      </Card>
    </div>
  );
}
