import { useEffect, useMemo, useState } from "react";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { useQuery } from "@tanstack/react-query";
import { Button, Card, CardDescription, CardTitle, EmptyState, FilterBar, FilterField, LoadingState } from "@qaongdur/ui";
import type { PlaybackSearchParams } from "@qaongdur/types";
import { useSearchParams } from "react-router-dom";
import { apiClient, queryKeys } from "../lib/api";
import {
  createRecentInputRangeInTimeZone,
  formatDateTimeInTimeZone,
  formatDateTimeInputForTimeZone,
  formatTimeInTimeZone,
  getOperatorTimeZoneLabel,
  parseDateTimeInputInTimeZone,
} from "../lib/bkk-time";
import { useOperatorOutlet } from "../app/use-operator-outlet";

const playbackBaseSchema = z
  .object({
    from: z.string().min(1),
    to: z.string().min(1),
    includeAlerts: z.boolean(),
  });

type PlaybackForm = z.infer<typeof playbackBaseSchema>;

export function PlaybackSearchPage() {
  const { cameras, selectedCameraIds, operatorTimeZone } = useOperatorOutlet();
  const playbackSchema = useMemo(
    () =>
      playbackBaseSchema.superRefine((values, context) => {
        const from = parseDateTimeInputInTimeZone(values.from, operatorTimeZone);
        const to = parseDateTimeInputInTimeZone(values.to, operatorTimeZone);

        if (!from) {
          context.addIssue({
            code: z.ZodIssueCode.custom,
            message: `Enter a valid ${getOperatorTimeZoneLabel(operatorTimeZone)} start time.`,
            path: ["from"],
          });
        }

        if (!to) {
          context.addIssue({
            code: z.ZodIssueCode.custom,
            message: `Enter a valid ${getOperatorTimeZoneLabel(operatorTimeZone)} end time.`,
            path: ["to"],
          });
        }

        if (from && to && from.getTime() >= to.getTime()) {
          context.addIssue({
            code: z.ZodIssueCode.custom,
            message: "`from` must be earlier than `to`",
            path: ["to"],
          });
        }
      }),
    [operatorTimeZone],
  );
  const [searchParams] = useSearchParams();
  const [initialWindow] = useState(() => {
    const range = createRecentInputRangeInTimeZone(operatorTimeZone);
    return {
      from: range.fromInput,
      to: range.toInput,
    };
  });
  const [activeParams, setActiveParams] = useState<PlaybackSearchParams | null>(null);
  const [selectedSegmentId, setSelectedSegmentId] = useState<string>();
  const [playbackCameraIds, setPlaybackCameraIds] = useState<string[]>(selectedCameraIds);

  const form = useForm<PlaybackForm>({
    resolver: zodResolver(playbackSchema),
    defaultValues: {
      from: initialWindow.from,
      to: initialWindow.to,
      includeAlerts: true,
    },
  });
  const timeZoneLabel = getOperatorTimeZoneLabel(operatorTimeZone);

  const playback = useQuery({
    queryKey: queryKeys.playback(JSON.stringify(activeParams ?? {})),
    queryFn: () => (activeParams ? apiClient.searchPlayback(activeParams) : Promise.resolve([])),
    enabled: Boolean(activeParams),
  });

  const cameraNameById = useMemo(
    () => new Map(cameras.map((camera) => [camera.id, camera.name])),
    [cameras],
  );
  const playbackPreset = useMemo<PlaybackSearchParams | null>(() => {
    const from = searchParams.get("from");
    const to = searchParams.get("to");
    const cameraId = searchParams.get("cameraId");
    const includeAlerts = searchParams.get("includeAlerts") !== "false";

    if (!from || !to) {
      return null;
    }

    const fromTimestamp = Date.parse(from);
    const toTimestamp = Date.parse(to);
    if (Number.isNaN(fromTimestamp) || Number.isNaN(toTimestamp) || fromTimestamp >= toTimestamp) {
      return null;
    }

    const cameraIds =
      cameraId && cameras.some((camera) => camera.id === cameraId) ? [cameraId] : [];

    return {
      cameraIds,
      from: new Date(fromTimestamp).toISOString(),
      to: new Date(toTimestamp).toISOString(),
      includeAlerts,
    };
  }, [cameras, searchParams]);

  useEffect(() => {
    const validCameraIds = new Set(cameras.map((camera) => camera.id));
    setPlaybackCameraIds((current) => {
      const next = current.filter((cameraId) => validCameraIds.has(cameraId));
      if (next.length) {
        return next;
      }
      return selectedCameraIds.filter((cameraId) => validCameraIds.has(cameraId));
    });
  }, [cameras, selectedCameraIds]);

  useEffect(() => {
    if (!playbackPreset) {
      return;
    }
    setPlaybackCameraIds(playbackPreset.cameraIds);
    form.reset({
      from: formatDateTimeInputForTimeZone(playbackPreset.from, operatorTimeZone),
      to: formatDateTimeInputForTimeZone(playbackPreset.to, operatorTimeZone),
      includeAlerts: playbackPreset.includeAlerts,
    });
    setActiveParams(playbackPreset);
  }, [form, operatorTimeZone, playbackPreset]);

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

  const togglePlaybackCamera = (cameraId: string) => {
    setPlaybackCameraIds((current) =>
      current.includes(cameraId)
        ? current.filter((selectedId) => selectedId !== cameraId)
        : [...current, cameraId],
    );
  };

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
        <p className="mt-4 text-xs text-[var(--qa-panel-text-subtle)]">
          {timeZoneLabel} with a 10 minute default window.
        </p>
        <Button
          size="sm"
          variant="secondary"
          onClick={form.handleSubmit((values) => {
            const from = parseDateTimeInputInTimeZone(values.from, operatorTimeZone);
            const to = parseDateTimeInputInTimeZone(values.to, operatorTimeZone);
            if (!from || !to) {
              return;
            }
            setActiveParams({
              cameraIds: playbackCameraIds,
              from: from.toISOString(),
              to: to.toISOString(),
              includeAlerts: values.includeAlerts,
            });
          })}
        >
          Search Playback
        </Button>
      </FilterBar>

      <Card className="space-y-3">
        <div className="flex items-center justify-between gap-3">
          <div>
            <CardTitle>Camera Selection</CardTitle>
            <CardDescription>
              Limit playback search to specific cameras, or leave all cameras selected.
            </CardDescription>
          </div>
          <Button
            size="sm"
            variant={playbackCameraIds.length ? "ghost" : "secondary"}
            onClick={() => setPlaybackCameraIds([])}
          >
            All cameras
          </Button>
        </div>
        <div className="flex flex-wrap gap-2">
          {cameras.map((camera) => {
            const selected = playbackCameraIds.includes(camera.id);
            return (
              <Button
                key={camera.id}
                size="sm"
                variant={selected ? "default" : "ghost"}
                onClick={() => togglePlaybackCamera(camera.id)}
                className="max-w-full min-w-0"
                title={camera.name}
              >
                <span className="block max-w-56 truncate">{camera.name}</span>
              </Button>
            );
          })}
        </div>
      </Card>

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
                      {formatTimeInTimeZone(segment.startAt, operatorTimeZone)} -{" "}
                      {formatTimeInTimeZone(segment.endAt, operatorTimeZone)}
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
                    ? `${cameraNameById.get(selectedSegment.cameraId) ?? selectedSegment.cameraId} • ${formatDateTimeInTimeZone(selectedSegment.startAt, operatorTimeZone)}`
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
