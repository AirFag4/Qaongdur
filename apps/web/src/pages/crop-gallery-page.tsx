import { useEffect, useMemo, useState } from "react";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
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
import type { CropTrackDetail, CropTrackFilter } from "@qaongdur/types";
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
const createDefaultRange = () => ({
  fromAt: toInputValue(new Date(Date.now() - 2 * 60 * 60 * 1000)),
  toAt: toInputValue(new Date()),
});
const PAGE_SIZE = 20;
type ObservationKey = "first" | "middle" | "last";
const OBSERVATION_OPTIONS: Array<{ key: ObservationKey; label: string }> = [
  { key: "first", label: "Start" },
  { key: "middle", label: "Middle" },
  { key: "last", label: "End" },
];

const toIsoOrUndefined = (value: string) => {
  if (!value) {
    return undefined;
  }
  const timestamp = Date.parse(value);
  return Number.isNaN(timestamp) ? undefined : new Date(timestamp).toISOString();
};

const buildFilter = ({
  cameraId,
  label,
  fromAt,
  toAt,
  includeRetired,
}: {
  cameraId: string;
  label: CropTrackFilter["label"];
  fromAt: string;
  toAt: string;
  includeRetired: boolean;
}): CropTrackFilter => ({
  cameraId: cameraId || undefined,
  label,
  fromAt: toIsoOrUndefined(fromAt),
  toAt: toIsoOrUndefined(toAt),
  includeRetired,
});

const observationFrameFor = (track: CropTrackDetail, key: ObservationKey) => {
  if (key === "first") {
    return {
      bbox: track.firstBBox,
      cropSrc: track.firstCropDataUrl,
      frameSrc: track.firstFrameDataUrl,
      happenedAt: track.firstSeenAt,
      offsetLabel: track.firstSeenOffsetLabel,
    };
  }
  if (key === "last") {
    return {
      bbox: track.lastBBox,
      cropSrc: track.lastCropDataUrl,
      frameSrc: track.lastFrameDataUrl,
      happenedAt: track.lastSeenAt,
      offsetLabel: track.lastSeenOffsetLabel,
    };
  }
  return {
    bbox: track.middleBBox,
    cropSrc: track.middleCropDataUrl,
    frameSrc: track.middleFrameDataUrl,
    happenedAt: track.middleSeenAt,
    offsetLabel: track.middleSeenOffsetLabel,
  };
};

const createPlaybackSearch = (track: CropTrackDetail) => {
  const from = track.segmentStartAt ?? track.firstSeenAt;
  const to =
    track.segmentStartAt && track.segmentDurationSec
      ? new Date(
          new Date(track.segmentStartAt).getTime() + track.segmentDurationSec * 1000,
        ).toISOString()
      : track.lastSeenAt;
  const params = new URLSearchParams({
    cameraId: track.cameraId,
    from,
    to,
    includeAlerts: "true",
  });
  return `/playback?${params.toString()}`;
};

function TrackObservationViewer({
  track,
  observationKey,
}: {
  track: CropTrackDetail;
  observationKey: ObservationKey;
}) {
  const observation = observationFrameFor(track, observationKey);
  const [loadedFrameSize, setLoadedFrameSize] = useState({ width: 0, height: 0 });
  const frameWidth =
    track.sourceFrameWidth && track.sourceFrameWidth > 0
      ? track.sourceFrameWidth
      : loadedFrameSize.width;
  const frameHeight =
    track.sourceFrameHeight && track.sourceFrameHeight > 0
      ? track.sourceFrameHeight
      : loadedFrameSize.height;
  const bbox = observation.bbox;
  const hasOverlay = Boolean(observation.frameSrc && bbox && frameWidth > 0 && frameHeight > 0);

  const overlayStyle =
    hasOverlay && bbox
      ? {
          left: `${(bbox[0] / frameWidth) * 100}%`,
          top: `${(bbox[1] / frameHeight) * 100}%`,
          width: `${((bbox[2] - bbox[0]) / frameWidth) * 100}%`,
          height: `${((bbox[3] - bbox[1]) / frameHeight) * 100}%`,
        }
      : undefined;

  return (
    <div className="grid gap-3 xl:grid-cols-[minmax(0,1.7fr)_220px]">
      <div className="space-y-2">
        <div className="flex items-center justify-between gap-2">
          <div>
            <p className="text-sm font-medium text-stone-100">
              {OBSERVATION_OPTIONS.find((option) => option.key === observationKey)?.label} observation
            </p>
            <p className="text-xs text-stone-400">
              {new Date(observation.happenedAt).toLocaleString()} • {observation.offsetLabel}
            </p>
          </div>
          <span className="rounded-full border border-stone-700 px-2 py-1 text-[11px] text-stone-300">
            {track.detectorLabel}
          </span>
        </div>
        <div className="relative aspect-video overflow-hidden rounded-md border border-stone-700 bg-stone-950">
          <img
            src={observation.frameSrc ?? observation.cropSrc}
            alt={`${track.cameraName} ${observationKey} observation`}
            className="h-full w-full object-contain"
            onLoad={(event) => {
              setLoadedFrameSize({
                width: event.currentTarget.naturalWidth,
                height: event.currentTarget.naturalHeight,
              });
            }}
          />
          {overlayStyle ? (
            <div
              className="pointer-events-none absolute border-2 border-cyan-400 shadow-[0_0_0_9999px_rgba(0,0,0,0.18)]"
              style={overlayStyle}
            >
              <span className="absolute left-0 top-0 -translate-y-full rounded bg-cyan-500/90 px-2 py-1 text-[11px] font-medium text-stone-950">
                {new Date(observation.happenedAt).toLocaleString()}
              </span>
            </div>
          ) : null}
        </div>
        {!observation.frameSrc ? (
          <p className="text-xs text-amber-300">
            Source frame overlay is not available for this track yet. Showing the stored crop instead.
          </p>
        ) : null}
      </div>

      <div className="space-y-2">
        <p className="text-xs uppercase tracking-wide text-stone-500">Stored crop</p>
        <div className="aspect-[4/5] overflow-hidden rounded-md border border-stone-700 bg-stone-950">
          <img
            src={observation.cropSrc}
            alt={`${track.cameraName} ${observationKey} crop`}
            className="h-full w-full object-cover"
          />
        </div>
        <div className="rounded-md border border-stone-700 bg-stone-950/60 p-3 text-xs text-stone-300">
          <div className="flex items-center justify-between gap-2">
            <span>Captured</span>
            <span>{new Date(observation.happenedAt).toLocaleTimeString()}</span>
          </div>
          <div className="mt-2 flex items-center justify-between gap-2">
            <span>Offset</span>
            <span>{observation.offsetLabel}</span>
          </div>
        </div>
      </div>
    </div>
  );
}

export function CropGalleryPage() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const defaultRange = useMemo(() => createDefaultRange(), []);
  const [cameraId, setCameraId] = useState<string>("");
  const [label, setLabel] = useState<CropTrackFilter["label"]>("all");
  const [fromAt, setFromAt] = useState(() => defaultRange.fromAt);
  const [toAt, setToAt] = useState(() => defaultRange.toAt);
  const [includeRetired, setIncludeRetired] = useState(false);
  const [currentPage, setCurrentPage] = useState(1);
  const [appliedFilter, setAppliedFilter] = useState<CropTrackFilter>(() =>
    buildFilter({
      cameraId: "",
      label: "all",
      fromAt: defaultRange.fromAt,
      toAt: defaultRange.toAt,
      includeRetired: false,
    }),
  );
  const [selectedTrackId, setSelectedTrackId] = useState<string>("");
  const [selectedObservation, setSelectedObservation] = useState<ObservationKey>("middle");

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

  const queryFilter = useMemo<CropTrackFilter>(
    () => ({
      ...appliedFilter,
      page: currentPage,
      pageSize: PAGE_SIZE,
    }),
    [appliedFilter, currentPage],
  );
  const appliedFilterKey = JSON.stringify(queryFilter);

  const tracks = useQuery({
    queryKey: queryKeys.cropTracks(appliedFilterKey),
    queryFn: () => apiClient.listCropTracks(queryFilter),
    refetchInterval: 10_000,
    placeholderData: keepPreviousData,
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
        queryClient.invalidateQueries({ queryKey: ["crop-tracks"] }),
        queryClient.invalidateQueries({ queryKey: queryKeys.visionSources }),
      ]);
    },
  });

  useEffect(() => {
    if (tracks.data && tracks.data.page !== currentPage) {
      setCurrentPage(tracks.data.page);
    }
  }, [currentPage, tracks.data]);

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

  const applyFilters = () => {
    setCurrentPage(1);
    setAppliedFilter(
      buildFilter({
        cameraId,
        label,
        fromAt,
        toAt,
        includeRetired,
      }),
    );
  };

  const resetFilters = () => {
    const nextRange = createDefaultRange();
    setCameraId("");
    setLabel("all");
    setFromAt(nextRange.fromAt);
    setToAt(nextRange.toAt);
    setIncludeRetired(false);
    setCurrentPage(1);
    setAppliedFilter(
      buildFilter({
        cameraId: "",
        label: "all",
        fromAt: nextRange.fromAt,
        toAt: nextRange.toAt,
        includeRetired: false,
      }),
    );
  };

  return (
    <div className="space-y-3">
      <FilterBar onReset={resetFilters}>
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
        <Button size="sm" variant="secondary" onClick={applyFilters}>
          Search Crops
        </Button>
        <label className="flex items-center gap-2 rounded-md border border-stone-700 bg-stone-950/40 px-3 py-2 text-xs text-stone-300">
          <input
            type="checkbox"
            className="accent-cyan-600"
            checked={includeRetired}
            onChange={(event) => setIncludeRetired(event.target.checked)}
          />
          Include retired history
        </label>
      </FilterBar>

      <div className="grid gap-3">
        <Card className="space-y-3">
          <div className="flex items-center justify-between gap-3">
            <div>
              <CardTitle>Track Gallery</CardTitle>
              <CardDescription>
                Representative crops from automatically processed recording chunks, filtered by real capture time.
                {!appliedFilter.includeRetired
                  ? " Showing current active sources only."
                  : " Including retired mock-source history."}
              </CardDescription>
            </div>
            <div className="text-right text-xs text-stone-400">
              <p>{tracks.data?.totalCount ?? 0} tracks</p>
              <p>
                Page {tracks.data?.page ?? 1} of {tracks.data?.totalPages ?? 1}
              </p>
              <p>Queue: {status.data?.queueDepth ?? 0}</p>
              <p>Workers: {status.data?.segmentWorkerCount ?? 1}</p>
            </div>
          </div>

          {!tracks.data?.tracks.length ? (
            <EmptyState
              title="No tracks in this window"
              description="Wait for recorded chunks to land or broaden the time range."
            />
          ) : (
            <div className="space-y-3">
              <div className="grid auto-rows-fr gap-3 md:grid-cols-2 2xl:grid-cols-4">
                {tracks.data.tracks.map((track) => (
                  <button
                    key={track.id}
                    type="button"
                    onClick={() => {
                      setSelectedTrackId(track.id);
                      setSelectedObservation("middle");
                    }}
                    className="rounded-md border border-stone-700 bg-stone-950/40 p-3 text-left transition-colors hover:border-stone-500"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <div className="min-w-0">
                        <CardTitle className="truncate text-sm">{track.cameraName}</CardTitle>
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

              <div className="flex items-center justify-between gap-3 rounded-md border border-stone-700 bg-stone-950/40 px-3 py-2 text-sm text-stone-300">
                <p>
                  Showing{" "}
                  {tracks.data.totalCount
                    ? (tracks.data.page - 1) * tracks.data.pageSize + 1
                    : 0}
                  -
                  {Math.min(
                    tracks.data.page * tracks.data.pageSize,
                    tracks.data.totalCount,
                  )}{" "}
                  of {tracks.data.totalCount}
                </p>
                <div className="flex items-center gap-2">
                  <Button
                    size="sm"
                    variant="ghost"
                    disabled={tracks.data.page <= 1}
                    onClick={() => setCurrentPage((page) => Math.max(page - 1, 1))}
                  >
                    Previous
                  </Button>
                  <Button
                    size="sm"
                    variant="secondary"
                    disabled={tracks.data.page >= tracks.data.totalPages}
                    onClick={() =>
                      setCurrentPage((page) =>
                        Math.min(page + 1, tracks.data?.totalPages ?? page),
                      )
                    }
                  >
                    Next
                  </Button>
                </div>
              </div>
            </div>
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

      {selectedTrackId ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm">
          <Card className="max-h-[92vh] w-full max-w-[1320px] overflow-auto border border-stone-700 bg-stone-900/95">
            <div className="sticky top-0 z-10 flex items-start justify-between gap-4 border-b border-stone-700 bg-stone-900/95 px-4 py-3">
              <div>
                <CardTitle>Track Investigation</CardTitle>
                <CardDescription>
                  Review the saved observation frames and overlays for this track.
                </CardDescription>
              </div>
              <Button size="sm" variant="ghost" onClick={() => setSelectedTrackId("")}>
                Close
              </Button>
            </div>

            <div className="p-4">
              {selectedTrack.isLoading ? (
                <LoadingState label="Loading track detail..." />
              ) : !selectedTrack.data ? (
                <EmptyState
                  title="Track unavailable"
                  description="The selected track could not be loaded."
                />
              ) : (
                <div className="space-y-4">
                  {(() => {
                    const track = selectedTrack.data;
                    return (
                      <>
                  <div className="flex flex-wrap items-center gap-2">
                    {OBSERVATION_OPTIONS.map((option) => (
                      <Button
                        key={option.key}
                        size="sm"
                        variant={selectedObservation === option.key ? "default" : "ghost"}
                        onClick={() => setSelectedObservation(option.key)}
                      >
                        {option.label}
                      </Button>
                    ))}
                  </div>

                  <TrackObservationViewer
                    track={track}
                    observationKey={selectedObservation}
                  />

                  <div className="grid gap-3 xl:grid-cols-[minmax(0,1.3fr)_360px]">
                    <Card className="space-y-3 border border-stone-700 bg-stone-950/50">
                      <div>
                        <CardTitle>Track Summary</CardTitle>
                        <CardDescription>
                          {track.cameraName} • {track.label}
                        </CardDescription>
                      </div>
                      <div className="flex flex-wrap gap-2">
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => navigate(`/live?cameraId=${encodeURIComponent(track.cameraId)}`)}
                        >
                          Open Live
                        </Button>
                        <Button
                          size="sm"
                          variant="secondary"
                          onClick={() => navigate(createPlaybackSearch(track))}
                        >
                          Open Playback Window
                        </Button>
                      </div>
                      <div className="grid gap-2 text-sm text-stone-300">
                        <div className="flex items-center justify-between gap-2">
                          <span>Segment start</span>
                          <span>
                            {track.segmentStartAt
                              ? new Date(track.segmentStartAt).toLocaleString()
                              : "n/a"}
                          </span>
                        </div>
                        <div className="flex items-center justify-between gap-2">
                          <span>Frames</span>
                          <span>
                            {track.frameCount} @ {track.sampleFps} fps
                          </span>
                        </div>
                        <div className="flex items-center justify-between gap-2">
                          <span>Embedding</span>
                          <span>
                            {track.embeddingStatus}
                            {track.embeddingDim
                              ? ` • ${track.embeddingDim}d`
                              : ""}
                          </span>
                        </div>
                        <div className="flex items-center justify-between gap-2">
                          <span>Face</span>
                          <span>
                            {track.faceStatus}
                            {track.faceDim ? ` • ${track.faceDim}d` : ""}
                          </span>
                        </div>
                        <div className="flex items-center justify-between gap-2">
                          <span>Closed</span>
                          <span>{track.closedReason}</span>
                        </div>
                      </div>
                    </Card>

                    <Card className="space-y-3 border border-stone-700 bg-stone-950/50">
                      <div>
                        <CardTitle>Saved Movement Points</CardTitle>
                        <CardDescription>
                          First, middle, and last point anchors for this track.
                        </CardDescription>
                      </div>
                      <div className="grid gap-2 text-xs text-stone-300">
                        <div className="flex items-center justify-between gap-2">
                          <span>First</span>
                          <span>
                            {track.firstPoint
                              ? `${track.firstPoint.x}, ${track.firstPoint.y}`
                              : "n/a"}
                          </span>
                        </div>
                        <div className="flex items-center justify-between gap-2">
                          <span>Middle</span>
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
                    </Card>
                  </div>
                      </>
                    );
                  })()}
                </div>
              )}
            </div>
          </Card>
        </div>
      ) : null}
    </div>
  );
}
