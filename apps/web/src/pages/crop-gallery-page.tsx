import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Button,
  Card,
  CardDescription,
  CardTitle,
  EmptyState,
  FilterBar,
  FilterField,
  LoadingState,
} from "@qaongdur/ui";
import type { CropTrackFilter } from "@qaongdur/types";
import { RoleGate } from "../auth/role-gate";
import { apiClient, queryKeys } from "../lib/api";

const formatBytes = (bytes: number) => {
  if (bytes >= 1024 * 1024 * 1024) {
    return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
  }
  if (bytes >= 1024 * 1024) {
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  }
  return `${bytes} B`;
};

const toInputValue = (date: Date) => date.toISOString().slice(0, 16);

export function CropGalleryPage() {
  const queryClient = useQueryClient();
  const [cameraId, setCameraId] = useState<string>("");
  const [label, setLabel] = useState<CropTrackFilter["label"]>("all");
  const [fromAt, setFromAt] = useState(() => toInputValue(new Date(Date.now() - 2 * 60 * 60 * 1000)));
  const [toAt, setToAt] = useState(() => toInputValue(new Date()));
  const [selectedTrackId, setSelectedTrackId] = useState<string>("");

  const status = useQuery({
    queryKey: queryKeys.visionStatus,
    queryFn: () => apiClient.getVisionStatus(),
    refetchInterval: 10_000,
  });

  const sources = useQuery({
    queryKey: queryKeys.visionSources,
    queryFn: () => apiClient.listVisionSources(),
    refetchInterval: 10_000,
  });

  const activeFilter = useMemo<CropTrackFilter>(
    () => ({
      cameraId: cameraId || undefined,
      label,
      fromAt: fromAt ? new Date(fromAt).toISOString() : undefined,
      toAt: toAt ? new Date(toAt).toISOString() : undefined,
    }),
    [cameraId, fromAt, label, toAt],
  );

  const tracks = useQuery({
    queryKey: queryKeys.cropTracks(JSON.stringify(activeFilter)),
    queryFn: () => apiClient.listCropTracks(activeFilter),
    refetchInterval: 10_000,
  });

  const selectedTrack = useQuery({
    queryKey: queryKeys.cropTrack(selectedTrackId),
    queryFn: () => apiClient.getCropTrack(selectedTrackId),
    enabled: Boolean(selectedTrackId),
  });

  const triggerScan = useMutation({
    mutationFn: () => apiClient.runVisionMockJob(),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: queryKeys.visionStatus }),
        queryClient.invalidateQueries({ queryKey: queryKeys.cropTracks(JSON.stringify(activeFilter)) }),
        queryClient.invalidateQueries({ queryKey: queryKeys.visionSources }),
      ]);
    },
  });

  useEffect(() => {
    if (!tracks.data?.length) {
      setSelectedTrackId("");
      return;
    }
    setSelectedTrackId((current) =>
      current && tracks.data.some((track) => track.id === current) ? current : tracks.data[0].id,
    );
  }, [tracks.data]);

  if (sources.isLoading || status.isLoading || tracks.isLoading) {
    return <LoadingState label="Loading tracked crops..." />;
  }

  if (sources.error || status.error || tracks.error) {
    return (
      <EmptyState
        title="Crop gallery unavailable"
        description="The vision API could not be reached."
      />
    );
  }

  return (
    <div className="space-y-3">
      <FilterBar>
        <FilterField label="Camera">
          <select
            className="form-input"
            value={cameraId}
            onChange={(event) => setCameraId(event.target.value)}
          >
            <option value="">All cameras</option>
            {sources.data?.map((source) => (
              <option key={source.id} value={source.cameraId}>
                {source.cameraName}
              </option>
            ))}
          </select>
        </FilterField>
        <FilterField label="Label">
          <select
            className="form-input"
            value={label ?? "all"}
            onChange={(event) => setLabel(event.target.value as CropTrackFilter["label"])}
          >
            <option value="all">All labels</option>
            <option value="person">Person</option>
            <option value="vehicle">Vehicle</option>
          </select>
        </FilterField>
        <FilterField label="From">
          <input
            type="datetime-local"
            className="form-input"
            value={fromAt}
            onChange={(event) => setFromAt(event.target.value)}
          />
        </FilterField>
        <FilterField label="To">
          <input
            type="datetime-local"
            className="form-input"
            value={toAt}
            onChange={(event) => setToAt(event.target.value)}
          />
        </FilterField>
        <RoleGate anyOf={["site-admin", "platform-admin"]}>
          <Button
            size="sm"
            variant="secondary"
            disabled={triggerScan.isPending}
            onClick={() => triggerScan.mutate()}
          >
            {triggerScan.isPending ? "Scanning..." : "Scan Recordings Now"}
          </Button>
        </RoleGate>
      </FilterBar>

      <div className="grid gap-3 xl:grid-cols-[minmax(0,1fr)_360px]">
        <Card className="space-y-3">
          <div className="flex items-center justify-between gap-3">
            <div>
              <CardTitle>Track Gallery</CardTitle>
              <CardDescription>
                Representative crops from automatically processed recording chunks, filtered by real capture time.
              </CardDescription>
            </div>
            <div className="text-right text-xs text-stone-400">
              <p>{tracks.data?.length ?? 0} tracks</p>
              <p>Queue: {status.data?.queueDepth ?? 0}</p>
            </div>
          </div>

          {!tracks.data?.length ? (
            <EmptyState
              title="No tracks in this window"
              description="Wait for recorded chunks to land or broaden the time range."
            />
          ) : (
            <div className="grid auto-rows-fr gap-3 md:grid-cols-2 2xl:grid-cols-3">
              {tracks.data.map((track) => (
                <button
                  key={track.id}
                  type="button"
                  onClick={() => setSelectedTrackId(track.id)}
                  className={`rounded-md border p-3 text-left transition-colors ${
                    selectedTrackId === track.id
                      ? "border-cyan-700 bg-cyan-950/20"
                      : "border-stone-700 bg-stone-950/40 hover:border-stone-500"
                  }`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <div>
                      <CardTitle className="text-sm">{track.cameraName}</CardTitle>
                      <CardDescription>
                        {track.label} • {track.detectorLabel}
                      </CardDescription>
                    </div>
                    <span className="rounded-full border border-stone-700 px-2 py-1 text-[11px] text-stone-300">
                      {Math.round(track.maxConfidence * 100)}%
                    </span>
                  </div>

                  <div className="mt-3 space-y-1">
                    <div className="aspect-[4/5] overflow-hidden rounded-md border border-stone-700 bg-stone-950">
                      <img
                        src={track.middleCropDataUrl}
                        alt={`${track.cameraName} representative crop`}
                        className="h-full w-full object-cover"
                      />
                    </div>
                    <p className="text-center text-[11px] text-stone-500">Representative crop</p>
                  </div>

                  <div className="mt-3 grid gap-2 text-[11px] text-stone-400">
                    <div className="flex items-center justify-between gap-2">
                      <span>First seen</span>
                      <span>{new Date(track.firstSeenAt).toLocaleString()}</span>
                    </div>
                    <div className="flex items-center justify-between gap-2">
                      <span>Last seen</span>
                      <span>{new Date(track.lastSeenAt).toLocaleString()}</span>
                    </div>
                    <div className="flex items-center justify-between gap-2">
                      <span>Frames</span>
                      <span>
                        {track.frameCount} @ {track.sampleFps} fps
                      </span>
                    </div>
                  </div>
                </button>
              ))}
            </div>
          )}
        </Card>

        <Card className="space-y-3">
          <div>
            <CardTitle>Track Detail</CardTitle>
            <CardDescription>
              First, main, and last points are preserved for each stored track.
            </CardDescription>
          </div>

          {!selectedTrackId ? (
            <EmptyState title="Select a track" description="Pick a crop card to inspect the saved movement points and metadata." />
          ) : selectedTrack.isLoading ? (
            <LoadingState label="Loading track detail..." />
          ) : !selectedTrack.data ? (
            <EmptyState title="Track unavailable" description="The selected track could not be loaded." />
          ) : (
            (() => {
              const track = selectedTrack.data;

              return (
            <div className="space-y-3">
              <div className="grid grid-cols-3 gap-2">
                {[
                  { label: "First", src: track.firstCropDataUrl },
                  { label: "Main", src: track.middleCropDataUrl },
                  { label: "Last", src: track.lastCropDataUrl },
                ].map((image) => (
                  <div key={image.label} className="space-y-1">
                    <div className="aspect-[4/5] overflow-hidden rounded-md border border-stone-700 bg-stone-950">
                      <img
                        src={image.src}
                        alt={`${track.cameraName} ${image.label.toLowerCase()} crop`}
                        className="h-full w-full object-cover"
                      />
                    </div>
                    <p className="text-center text-[11px] text-stone-500">{image.label}</p>
                  </div>
                ))}
              </div>

              <div className="grid gap-2 text-sm text-stone-300">
                <div className="flex items-center justify-between gap-2">
                  <span>Camera</span>
                  <span>{track.cameraName}</span>
                </div>
                <div className="flex items-center justify-between gap-2">
                  <span>Track label</span>
                  <span>{track.label}</span>
                </div>
                <div className="flex items-center justify-between gap-2">
                  <span>Segment start</span>
                  <span>{track.segmentStartAt ? new Date(track.segmentStartAt).toLocaleString() : "n/a"}</span>
                </div>
                <div className="flex items-center justify-between gap-2">
                  <span>Embedding</span>
                  <span>
                    {track.embeddingStatus}
                    {track.embeddingDim ? ` • ${track.embeddingDim}d` : ""}
                  </span>
                </div>
                <div className="flex items-center justify-between gap-2">
                  <span>Face</span>
                  <span>
                    {track.faceStatus}
                    {track.faceDim ? ` • ${track.faceDim}d` : ""}
                  </span>
                </div>
              </div>

              <div className="rounded-md border border-stone-700 bg-stone-950/60 p-3 text-sm text-stone-300">
                <p className="mb-2 text-xs uppercase tracking-wide text-stone-500">Saved movement points</p>
                <div className="grid gap-2 text-xs">
                  <div className="flex items-center justify-between gap-2">
                    <span>First</span>
                    <span>
                      {track.firstPoint
                        ? `${track.firstPoint.x}, ${track.firstPoint.y}`
                        : "n/a"}
                    </span>
                  </div>
                  <div className="flex items-center justify-between gap-2">
                    <span>Main</span>
                    <span>
                      {track.middlePoint
                        ? `${track.middlePoint.x}, ${track.middlePoint.y}`
                        : "n/a"}
                    </span>
                  </div>
                  <div className="flex items-center justify-between gap-2">
                    <span>Last</span>
                    <span>
                      {track.lastPoint
                        ? `${track.lastPoint.x}, ${track.lastPoint.y}`
                        : "n/a"}
                    </span>
                  </div>
                </div>
              </div>
            </div>
              );
            })()
          )}
        </Card>
      </div>

      <Card className="space-y-3">
        <div>
          <CardTitle>Vision Status</CardTitle>
          <CardDescription>
            Automatic processing runs against finalized MediaMTX recording chunks, not the original mock files.
          </CardDescription>
        </div>

        <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-4">
          <div className="rounded-md border border-stone-700 bg-stone-950/60 p-3 text-sm text-stone-300">
            <p className="text-xs uppercase tracking-wide text-stone-500">Latest job</p>
            <p className="mt-1">{status.data?.latestJob?.status ?? "idle"}</p>
          </div>
          <div className="rounded-md border border-stone-700 bg-stone-950/60 p-3 text-sm text-stone-300">
            <p className="text-xs uppercase tracking-wide text-stone-500">Storage used</p>
            <p className="mt-1">{formatBytes(status.data?.storage.usedBytes ?? 0)}</p>
          </div>
          <div className="rounded-md border border-stone-700 bg-stone-950/60 p-3 text-sm text-stone-300">
            <p className="text-xs uppercase tracking-wide text-stone-500">Detector</p>
            <p className="mt-1">{status.data?.detector.modelName}</p>
          </div>
          <div className="rounded-md border border-stone-700 bg-stone-950/60 p-3 text-sm text-stone-300">
            <p className="text-xs uppercase tracking-wide text-stone-500">Vector store</p>
            <p className="mt-1">{status.data?.vectorStore?.provider ?? "n/a"}</p>
          </div>
        </div>
      </Card>
    </div>
  );
}
