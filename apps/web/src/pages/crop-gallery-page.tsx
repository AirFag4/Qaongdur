import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type ChangeEvent,
  type DragEvent,
} from "react";
import {
  keepPreviousData,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { useNavigate, useSearchParams } from "react-router-dom";
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
import type {
  CropTrackDetail,
  CropTrackFilter,
  CropTrackSearchInput,
} from "@qaongdur/types";
import { RoleGate } from "../auth/role-gate";
import { useOperatorOutlet } from "../app/use-operator-outlet";
import { apiClient, queryKeys } from "../lib/api";
import {
  createRecentInputRangeInTimeZone,
  formatDateTimeInTimeZone,
  formatDateTimeInputForTimeZone,
  formatTimeInTimeZone,
  getOperatorTimeZoneLabel,
  type OperatorTimeZonePreference,
  toIsoOrUndefinedInTimeZone,
} from "../lib/bkk-time";

const formatBytes = (bytes: number) => {
  if (bytes >= 1024 * 1024 * 1024) {
    return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
  }
  if (bytes >= 1024 * 1024) {
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  }
  return `${bytes} B`;
};

const createDefaultRange = (
  operatorTimeZone: OperatorTimeZonePreference,
) => {
  const range = createRecentInputRangeInTimeZone(operatorTimeZone);
  return {
    fromAt: range.fromInput,
    toAt: range.toInput,
  };
};
const PAGE_SIZE = 20;
type ObservationKey = "first" | "middle" | "last";
const OBSERVATION_OPTIONS: Array<{ key: ObservationKey; label: string }> = [
  { key: "first", label: "Start" },
  { key: "middle", label: "Middle" },
  { key: "last", label: "End" },
];

const fingerprintString = (value: string) => {
  let hash = 0;
  for (let index = 0; index < value.length; index += 1) {
    hash = (hash * 31 + value.charCodeAt(index)) >>> 0;
  }
  return hash.toString(16);
};

const readFileAsDataUrl = (file: File) =>
  new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      if (typeof reader.result === "string") {
        resolve(reader.result);
        return;
      }
      reject(new Error("Unable to read the selected image."));
    };
    reader.onerror = () => reject(reader.error ?? new Error("Unable to read the selected image."));
    reader.readAsDataURL(file);
  });

const buildFilter = ({
  cameraId,
  label,
  fromAt,
  toAt,
  includeRetired,
  operatorTimeZone,
}: {
  cameraId: string;
  label: CropTrackFilter["label"];
  fromAt: string;
  toAt: string;
  includeRetired: boolean;
  operatorTimeZone: OperatorTimeZonePreference;
}): CropTrackFilter => ({
  cameraId: cameraId || undefined,
  label,
  fromAt: toIsoOrUndefinedInTimeZone(fromAt, operatorTimeZone),
  toAt: toIsoOrUndefinedInTimeZone(toAt, operatorTimeZone),
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

const computeContainedImageRect = ({
  boxWidth,
  boxHeight,
  assetWidth,
  assetHeight,
}: {
  boxWidth: number;
  boxHeight: number;
  assetWidth: number;
  assetHeight: number;
}) => {
  if (boxWidth <= 0 || boxHeight <= 0 || assetWidth <= 0 || assetHeight <= 0) {
    return {
      left: 0,
      top: 0,
      width: 0,
      height: 0,
    };
  }

  const scale = Math.min(boxWidth / assetWidth, boxHeight / assetHeight);
  const width = assetWidth * scale;
  const height = assetHeight * scale;

  return {
    left: (boxWidth - width) / 2,
    top: (boxHeight - height) / 2,
    width,
    height,
  };
};

const createPlaybackSearch = (track: CropTrackDetail) => {
  const from = track.segmentStartAt ?? track.firstSeenAt;
  const to =
    track.segmentStartAt && track.segmentDurationSec
      ? new Date(
          new Date(track.segmentStartAt).getTime() +
            track.segmentDurationSec * 1000,
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
  isDarkTheme,
  operatorTimeZone,
}: {
  track: CropTrackDetail;
  observationKey: ObservationKey;
  isDarkTheme: boolean;
  operatorTimeZone: OperatorTimeZonePreference;
}) {
  const observation = observationFrameFor(track, observationKey);
  const frameImageRef = useRef<HTMLImageElement | null>(null);
  const [loadedFrameSize, setLoadedFrameSize] = useState({
    width: 0,
    height: 0,
  });
  const [renderedFrameRect, setRenderedFrameRect] = useState({
    left: 0,
    top: 0,
    width: 0,
    height: 0,
  });
  const frameWidth =
    track.sourceFrameWidth && track.sourceFrameWidth > 0
      ? track.sourceFrameWidth
      : loadedFrameSize.width;
  const frameHeight =
    track.sourceFrameHeight && track.sourceFrameHeight > 0
      ? track.sourceFrameHeight
      : loadedFrameSize.height;
  const bbox = observation.bbox;
  const hasOverlay = Boolean(
    observation.frameSrc && bbox && frameWidth > 0 && frameHeight > 0,
  );
  const frameAspectRatio =
    frameWidth > 0 && frameHeight > 0
      ? `${frameWidth} / ${frameHeight}`
      : "16 / 9";

  useEffect(() => {
    const image = frameImageRef.current;
    if (!image) {
      return undefined;
    }

    const syncRenderedFrameRect = () => {
      const assetWidth = frameWidth > 0 ? frameWidth : image.naturalWidth;
      const assetHeight = frameHeight > 0 ? frameHeight : image.naturalHeight;
      setRenderedFrameRect(
        computeContainedImageRect({
          boxWidth: image.clientWidth,
          boxHeight: image.clientHeight,
          assetWidth,
          assetHeight,
        }),
      );
    };

    syncRenderedFrameRect();

    if (typeof ResizeObserver === "undefined") {
      window.addEventListener("resize", syncRenderedFrameRect);
      return () => window.removeEventListener("resize", syncRenderedFrameRect);
    }

    const observer = new ResizeObserver(syncRenderedFrameRect);
    observer.observe(image);

    return () => observer.disconnect();
  }, [frameHeight, frameWidth, observation.frameSrc, observation.cropSrc]);

  const overlayStyle =
    hasOverlay && bbox && renderedFrameRect.width > 0 && renderedFrameRect.height > 0
      ? (() => {
          const x1 = Math.max(0, Math.min(bbox[0], frameWidth));
          const y1 = Math.max(0, Math.min(bbox[1], frameHeight));
          const x2 = Math.max(x1, Math.min(bbox[2], frameWidth));
          const y2 = Math.max(y1, Math.min(bbox[3], frameHeight));

          return {
            left: renderedFrameRect.left + (x1 / frameWidth) * renderedFrameRect.width,
            top: renderedFrameRect.top + (y1 / frameHeight) * renderedFrameRect.height,
            width: ((x2 - x1) / frameWidth) * renderedFrameRect.width,
            height: ((y2 - y1) / frameHeight) * renderedFrameRect.height,
          };
        })()
      : undefined;

  return (
    <div className="grid gap-3 xl:grid-cols-[minmax(0,1.7fr)_220px]">
      <div className="space-y-2">
        <div className="flex items-center justify-between gap-2">
          <div>
            <p
              className={
                isDarkTheme
                  ? "text-sm font-medium text-stone-100"
                  : "text-sm font-medium text-slate-900"
              }
            >
              {
                OBSERVATION_OPTIONS.find(
                  (option) => option.key === observationKey,
                )?.label
              }{" "}
              observation
            </p>
            <p
              className={
                isDarkTheme
                  ? "text-xs text-stone-400"
                  : "text-xs text-slate-500"
              }
            >
              {formatDateTimeInTimeZone(observation.happenedAt, operatorTimeZone, {
                includeSeconds: true,
              })} •{" "}
              {observation.offsetLabel}
            </p>
          </div>
          <span
            className={
              isDarkTheme
                ? "rounded-full border border-stone-700 px-2 py-1 text-[11px] text-stone-300"
                : "rounded-full border border-slate-300 px-2 py-1 text-[11px] text-slate-600"
            }
          >
            {track.detectorLabel}
          </span>
        </div>
        <div
          className={
            isDarkTheme
              ? "flex min-h-[240px] items-center justify-center overflow-hidden rounded-md border border-stone-700 bg-stone-950 p-2"
              : "flex min-h-[240px] items-center justify-center overflow-hidden rounded-md border border-slate-300 bg-white p-2"
          }
        >
          <div className="relative w-full" style={{ aspectRatio: frameAspectRatio }}>
            <img
              ref={frameImageRef}
              src={observation.frameSrc ?? observation.cropSrc}
              alt={`${track.cameraName} ${observationKey} observation`}
              className="block h-full w-full object-contain"
              onLoad={(event) => {
                setLoadedFrameSize({
                  width: event.currentTarget.naturalWidth,
                  height: event.currentTarget.naturalHeight,
                });
                const assetWidth =
                  frameWidth > 0 ? frameWidth : event.currentTarget.naturalWidth;
                const assetHeight =
                  frameHeight > 0 ? frameHeight : event.currentTarget.naturalHeight;
                setRenderedFrameRect(
                  computeContainedImageRect({
                    boxWidth: event.currentTarget.clientWidth,
                    boxHeight: event.currentTarget.clientHeight,
                    assetWidth,
                    assetHeight,
                  }),
                );
              }}
            />
            {overlayStyle ? (
              <div
                className="pointer-events-none absolute border-2 border-cyan-400 shadow-[0_0_0_9999px_rgba(0,0,0,0.18)]"
                style={overlayStyle}
              >
                <span className="absolute left-0 top-0 -translate-y-full rounded bg-cyan-500/90 px-2 py-1 text-[11px] font-medium text-stone-950">
                  {formatDateTimeInTimeZone(observation.happenedAt, operatorTimeZone, {
                    includeSeconds: true,
                  })}
                </span>
              </div>
            ) : null}
          </div>
        </div>
        {!observation.frameSrc ? (
          <p className="text-xs text-amber-300">
            Source frame overlay is not available for this track yet. Showing
            the stored crop instead.
          </p>
        ) : null}
      </div>

      <div className="space-y-2">
        <p
          className={
            isDarkTheme
              ? "text-xs uppercase tracking-wide text-stone-500"
              : "text-xs uppercase tracking-wide text-slate-500"
          }
        >
          Stored crop
        </p>
        <div
          className={
            isDarkTheme
              ? "flex aspect-[4/5] items-center justify-center overflow-hidden rounded-md border border-stone-700 bg-stone-950 p-2"
              : "flex aspect-[4/5] items-center justify-center overflow-hidden rounded-md border border-slate-300 bg-white p-2"
          }
        >
          <img
            src={observation.cropSrc}
            alt={`${track.cameraName} ${observationKey} crop`}
            className="h-full w-full object-contain"
          />
        </div>
        <div
          className={
            isDarkTheme
              ? "rounded-md border border-stone-700 bg-stone-950/60 p-3 text-xs text-stone-300"
              : "rounded-md border border-slate-300 bg-slate-100 p-3 text-xs text-slate-700"
          }
        >
          <div className="flex items-center justify-between gap-2">
            <span>Captured</span>
            <span>{formatTimeInTimeZone(observation.happenedAt, operatorTimeZone)}</span>
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

function FacePreviewCard({
  title,
  description,
  imageSrc,
  isDarkTheme,
}: {
  title: string;
  description: string;
  imageSrc?: string | null;
  isDarkTheme: boolean;
}) {
  return (
    <div
      className={
        isDarkTheme
          ? "space-y-2 rounded-md border border-stone-700 bg-stone-950/60 p-3"
          : "space-y-2 rounded-md border border-slate-300 bg-slate-100/70 p-3"
      }
    >
      <div>
        <p
          className={
            isDarkTheme
              ? "text-sm font-medium text-stone-100"
              : "text-sm font-medium text-slate-900"
          }
        >
          {title}
        </p>
        <p
          className={
            isDarkTheme ? "text-xs text-stone-400" : "text-xs text-slate-500"
          }
        >
          {description}
        </p>
      </div>
      <div
        className={
          isDarkTheme
            ? "flex aspect-square items-center justify-center overflow-hidden rounded-md border border-stone-700 bg-stone-950"
            : "flex aspect-square items-center justify-center overflow-hidden rounded-md border border-slate-300 bg-white"
        }
      >
        {imageSrc ? (
          <img
            src={imageSrc}
            alt={title}
            className="h-full w-full object-contain"
          />
        ) : (
          <span
            className={
              isDarkTheme ? "text-xs text-stone-500" : "text-xs text-slate-500"
            }
          >
            Not available
          </span>
        )}
      </div>
    </div>
  );
}

export function CropGalleryPage() {
  const queryClient = useQueryClient();
  const { themeMode, operatorTimeZone } = useOperatorOutlet();
  const isDarkTheme = themeMode === "polarized-dark";
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const defaultRange = useMemo(
    () => createDefaultRange(operatorTimeZone),
    [operatorTimeZone],
  );
  const timeZoneLabel = getOperatorTimeZoneLabel(operatorTimeZone);
  const initialCameraId = searchParams.get("cameraId") ?? "";
  const initialFrom = searchParams.get("fromAt") ?? searchParams.get("from");
  const initialTo = searchParams.get("toAt") ?? searchParams.get("to");
  const initialFromInput =
    initialFrom && !Number.isNaN(Date.parse(initialFrom))
      ? formatDateTimeInputForTimeZone(initialFrom, operatorTimeZone)
      : defaultRange.fromAt;
  const initialToInput =
    initialTo && !Number.isNaN(Date.parse(initialTo))
      ? formatDateTimeInputForTimeZone(initialTo, operatorTimeZone)
      : defaultRange.toAt;
  const [cameraId, setCameraId] = useState<string>(initialCameraId);
  const [label, setLabel] = useState<CropTrackFilter["label"]>("all");
  const [fromAt, setFromAt] = useState(() => initialFromInput);
  const [toAt, setToAt] = useState(() => initialToInput);
  const [textQuery, setTextQuery] = useState("");
  const [imageQueryName, setImageQueryName] = useState("");
  const [imageQueryDataUrl, setImageQueryDataUrl] = useState("");
  const [isImageDragActive, setIsImageDragActive] = useState(false);
  const [includeRetired, setIncludeRetired] = useState(false);
  const [currentPage, setCurrentPage] = useState(1);
  const imageInputRef = useRef<HTMLInputElement | null>(null);
  const [appliedFilter, setAppliedFilter] = useState<CropTrackFilter>(() =>
      buildFilter({
      cameraId: initialCameraId,
      label: "all",
      fromAt: initialFromInput,
      toAt: initialToInput,
      includeRetired: false,
      operatorTimeZone,
    }),
  );
  const [appliedSearch, setAppliedSearch] = useState<CropTrackSearchInput>({});
  const [selectedTrackId, setSelectedTrackId] = useState<string>("");
  const [selectedObservation, setSelectedObservation] =
    useState<ObservationKey>("middle");

  const clearImageQuery = () => {
    setImageQueryName("");
    setImageQueryDataUrl("");
    if (imageInputRef.current) {
      imageInputRef.current.value = "";
    }
  };

  const applyImageFile = async (file?: File) => {
    if (!file) {
      clearImageQuery();
      return;
    }
    try {
      const dataUrl = await readFileAsDataUrl(file);
      setImageQueryName(file.name);
      setImageQueryDataUrl(dataUrl);
    } catch {
      clearImageQuery();
    }
  };

  const status = useQuery({
    queryKey: queryKeys.visionStatus,
    queryFn: () => apiClient.getVisionStatus(),
    refetchInterval: 10_000,
  });
  const embeddingState = status.data?.embedding.state;
  const textSearchHint =
    embeddingState === "disabled" || embeddingState === "fallback"
      ? "Text currently falls back to metadata ranking on this runtime; image search still runs face-first."
      : embeddingState === "pending" || embeddingState === "initializing"
        ? "Text search will initialize MobileCLIP on first use; the first semantic query can take longer."
        : "Text uses text-to-image similarity; text + image searches are merged.";

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
  const activeCropSearch = useMemo<CropTrackSearchInput>(
    () => ({
      ...queryFilter,
      textQuery: appliedSearch.textQuery,
      imageBase64: appliedSearch.imageBase64,
    }),
    [appliedSearch.imageBase64, appliedSearch.textQuery, queryFilter],
  );
  const hasSemanticSearch = Boolean(
    activeCropSearch.textQuery?.trim() || activeCropSearch.imageBase64?.trim(),
  );
  const appliedFilterKey = JSON.stringify({
    ...activeCropSearch,
    imageBase64: activeCropSearch.imageBase64
      ? `hash:${fingerprintString(activeCropSearch.imageBase64)}`
      : undefined,
  });

  const tracks = useQuery({
    queryKey: queryKeys.cropTracks(appliedFilterKey),
    queryFn: () =>
      hasSemanticSearch
        ? apiClient.searchCropTracks(activeCropSearch)
        : apiClient.listCropTracks(queryFilter),
    refetchInterval: hasSemanticSearch ? false : 10_000,
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
        operatorTimeZone,
      }),
    );
    setAppliedSearch({
      textQuery: textQuery.trim() || undefined,
      imageBase64: imageQueryDataUrl || undefined,
    });
  };

  const resetFilters = () => {
    const nextRange = createDefaultRange(operatorTimeZone);
    setCameraId("");
    setLabel("all");
    setFromAt(nextRange.fromAt);
    setToAt(nextRange.toAt);
    setTextQuery("");
    clearImageQuery();
    setIncludeRetired(false);
    setCurrentPage(1);
    setAppliedFilter(
      buildFilter({
        cameraId: "",
        label: "all",
        fromAt: nextRange.fromAt,
        toAt: nextRange.toAt,
        includeRetired: false,
        operatorTimeZone,
      }),
    );
    setAppliedSearch({});
  };

  const handleImageSelection = async (
    event: ChangeEvent<HTMLInputElement>,
  ) => {
    await applyImageFile(event.target.files?.[0]);
  };

  const handleImageDrop = async (event: DragEvent<HTMLLabelElement>) => {
    event.preventDefault();
    setIsImageDragActive(false);
    await applyImageFile(event.dataTransfer.files?.[0]);
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
            onChange={(event) =>
              setLabel(event.target.value as CropTrackFilter["label"])
            }
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
        <FilterField label="Text Search">
          <input
            type="text"
            className="form-input"
            value={textQuery}
            placeholder="Describe person, vehicle, or scene"
            onChange={(event) => setTextQuery(event.target.value)}
          />
        </FilterField>
        <FilterField label="Image Search">
          <div className="space-y-2">
            <label
              className={
                isImageDragActive
                  ? "flex cursor-pointer flex-col items-center justify-center gap-2 rounded-md border border-cyan-500 bg-cyan-500/10 px-4 py-4 text-center"
                  : "flex cursor-pointer flex-col items-center justify-center gap-2 rounded-md border border-dashed border-[var(--qa-panel-border)] bg-[var(--qa-panel-muted)]/40 px-4 py-4 text-center"
              }
              onDragOver={(event) => {
                event.preventDefault();
                setIsImageDragActive(true);
              }}
              onDragLeave={() => setIsImageDragActive(false)}
              onDrop={(event) => void handleImageDrop(event)}
            >
              <input
                ref={imageInputRef}
                type="file"
                accept="image/*"
                className="hidden"
                onChange={(event) => void handleImageSelection(event)}
              />
              {imageQueryDataUrl ? (
                <div className="space-y-2">
                  <div className="mx-auto flex h-28 w-28 items-center justify-center overflow-hidden rounded-md border border-[var(--qa-panel-border)] bg-[var(--qa-panel-bg)]">
                    <img
                      src={imageQueryDataUrl}
                      alt={imageQueryName || "Selected image query"}
                      className="h-full w-full object-contain"
                    />
                  </div>
                  <p className="text-xs text-[var(--qa-panel-text-subtle)]">
                    Click or drop another image to replace it.
                  </p>
                </div>
              ) : (
                <>
                  <p className="text-sm font-medium text-[var(--qa-panel-text)]">
                    Drag a face or person image here
                  </p>
                  <p className="text-xs text-[var(--qa-panel-text-subtle)]">
                    Or click to upload an image for face-first search.
                  </p>
                </>
              )}
            </label>
            {imageQueryName ? (
              <div className="flex items-center gap-2 text-xs text-[var(--qa-panel-text-subtle)]">
                <span className="truncate">{imageQueryName}</span>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={clearImageQuery}
                >
                  Clear
                </Button>
              </div>
            ) : (
              <p className="text-xs text-[var(--qa-panel-text-subtle)]">
                Face is attempted first. If no face is found, image similarity falls back to object embeddings.
              </p>
            )}
          </div>
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
        <p className="text-xs text-[var(--qa-panel-text-subtle)]">
          {timeZoneLabel} with a 10 minute default window. {textSearchHint}
        </p>
        <label
          className={
            isDarkTheme
              ? "flex items-center gap-2 rounded-md border border-stone-700 bg-stone-950/40 px-3 py-2 text-xs text-stone-300"
              : "flex items-center gap-2 rounded-md border border-slate-300 bg-white/80 px-3 py-2 text-xs text-slate-700"
          }
        >
          <input
            type="checkbox"
            className="accent-cyan-600"
            checked={includeRetired}
            onChange={(event) => setIncludeRetired(event.target.checked)}
          />
          Include retired history
        </label>
      </FilterBar>

      {appliedSearch.imageBase64 ? (
        <Card className="space-y-3">
          <div className="flex items-center justify-between gap-3">
            <div>
              <CardTitle>Image Query Review</CardTitle>
              <CardDescription>
                Uploaded image, detected face crop, and aligned face preview for
                the current search.
              </CardDescription>
            </div>
            {tracks.data?.imageQueryDebug ? (
              <div className="theme-panel-caption text-right text-xs">
                <p>Face status: {tracks.data.imageQueryDebug.faceStatus}</p>
                <p>Faces found: {tracks.data.imageQueryDebug.faceCount}</p>
              </div>
            ) : null}
          </div>

          <div className="grid gap-3 md:grid-cols-3">
            <FacePreviewCard
              title="Uploaded Query"
              description="The image currently driving the search request."
              imageSrc={appliedSearch.imageBase64}
              isDarkTheme={isDarkTheme}
            />
            <FacePreviewCard
              title="Detected Face"
              description="The padded face crop selected for face search."
              imageSrc={tracks.data?.imageQueryDebug?.detectedFaceDataUrl}
              isDarkTheme={isDarkTheme}
            />
            <FacePreviewCard
              title="Aligned Face"
              description="Face alignment preview before embedding extraction."
              imageSrc={tracks.data?.imageQueryDebug?.alignedFaceDataUrl}
              isDarkTheme={isDarkTheme}
            />
          </div>

          {tracks.data?.imageQueryDebug?.detail ? (
            <p className="theme-panel-caption text-xs">
              {tracks.data.imageQueryDebug.detail}
            </p>
          ) : null}
        </Card>
      ) : null}

      <div className="grid gap-3">
        <Card className="space-y-3">
          <div className="flex items-center justify-between gap-3">
            <div>
              <CardTitle>Track Gallery</CardTitle>
              <CardDescription>
                Representative crops from automatically processed recording
                chunks, filtered by real capture time.
                {!appliedFilter.includeRetired
                  ? " Showing current active sources only."
                  : " Including retired mock-source history."}
              </CardDescription>
            </div>
            <div className="theme-panel-caption text-right text-xs">
              <p>{tracks.data?.totalCount ?? 0} tracks</p>
              <p>
                Page {tracks.data?.page ?? 1} of {tracks.data?.totalPages ?? 1}
              </p>
              {tracks.data?.searchModes?.length ? (
                <p>Search: {tracks.data.searchModes.join(", ")}</p>
              ) : null}
              <p>Queue: {status.data?.queueDepth ?? 0}</p>
              <p>Workers: {status.data?.segmentWorkerCount ?? 1}</p>
            </div>
          </div>

          {!tracks.data?.tracks.length ? (
            <EmptyState
              title="No tracks in this window"
              description={
                hasSemanticSearch
                  ? "No tracks matched the current text/image search inside this filter window."
                  : "Wait for recorded chunks to land or broaden the time range."
              }
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
                    className="theme-panel-subtle p-3 text-left transition-colors hover:border-cyan-600/60"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <div className="min-w-0">
                        <CardTitle className="truncate text-sm">
                          {track.cameraName}
                        </CardTitle>
                        <CardDescription>
                          {track.label} • {track.detectorLabel}
                        </CardDescription>
                      </div>
                      <span className="theme-panel-muted px-2 py-1 text-[11px]">
                        {Math.round(track.maxConfidence * 100)}%
                      </span>
                    </div>

                    <div className="mt-3 space-y-1">
                      <div className="theme-panel-muted flex aspect-[4/5] items-center justify-center overflow-hidden p-2">
                        <img
                          src={track.middleCropDataUrl}
                          alt={`${track.cameraName} representative crop`}
                          className="h-full w-full object-contain"
                        />
                      </div>
                      <p className="theme-panel-caption text-center text-[11px]">
                        Representative crop
                      </p>
                    </div>

                    <div className="theme-panel-description mt-3 grid gap-2 text-[11px]">
                      <div className="flex items-center justify-between gap-2">
                        <span>First seen</span>
                        <span>
                          {formatDateTimeInTimeZone(track.firstSeenAt, operatorTimeZone)}
                        </span>
                      </div>
                      <div className="flex items-center justify-between gap-2">
                        <span>Last seen</span>
                        <span>
                          {formatDateTimeInTimeZone(track.lastSeenAt, operatorTimeZone)}
                        </span>
                      </div>
                      <div className="flex items-center justify-between gap-2">
                        <span>Frames</span>
                        <span>
                          {track.frameCount} @ {track.sampleFps} fps
                        </span>
                      </div>
                      {track.searchReason ? (
                        <div className="flex items-center justify-between gap-2">
                          <span>Match</span>
                          <span>
                            {track.searchReason}
                            {typeof track.searchScore === "number"
                              ? ` • ${(track.searchScore * 100).toFixed(1)}%`
                              : ""}
                          </span>
                        </div>
                      ) : null}
                    </div>
                  </button>
                ))}
              </div>

              <div className="theme-panel-subtle flex items-center justify-between gap-3 px-3 py-2 text-sm">
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
                    onClick={() =>
                      setCurrentPage((page) => Math.max(page - 1, 1))
                    }
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
            Automatic processing runs against finalized MediaMTX recording
            chunks, not the original mock files.
          </CardDescription>
        </div>

        <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-4">
          <div
            className={
              isDarkTheme
                ? "rounded-md border border-stone-700 bg-stone-950/60 p-3 text-sm text-stone-300"
                : "rounded-md border border-slate-300 bg-white/85 p-3 text-sm text-slate-700"
            }
          >
            <p
              className={
                isDarkTheme
                  ? "text-xs uppercase tracking-wide text-stone-500"
                  : "text-xs uppercase tracking-wide text-slate-500"
              }
            >
              Latest job
            </p>
            <p className="mt-1">{status.data?.latestJob?.status ?? "idle"}</p>
          </div>
          <div
            className={
              isDarkTheme
                ? "rounded-md border border-stone-700 bg-stone-950/60 p-3 text-sm text-stone-300"
                : "rounded-md border border-slate-300 bg-white/85 p-3 text-sm text-slate-700"
            }
          >
            <p
              className={
                isDarkTheme
                  ? "text-xs uppercase tracking-wide text-stone-500"
                  : "text-xs uppercase tracking-wide text-slate-500"
              }
            >
              Storage used
            </p>
            <p className="mt-1">
              {formatBytes(status.data?.storage.usedBytes ?? 0)}
            </p>
          </div>
          <div
            className={
              isDarkTheme
                ? "rounded-md border border-stone-700 bg-stone-950/60 p-3 text-sm text-stone-300"
                : "rounded-md border border-slate-300 bg-white/85 p-3 text-sm text-slate-700"
            }
          >
            <p
              className={
                isDarkTheme
                  ? "text-xs uppercase tracking-wide text-stone-500"
                  : "text-xs uppercase tracking-wide text-slate-500"
              }
            >
              Detector
            </p>
            <p className="mt-1">{status.data?.detector.modelName}</p>
          </div>
          <div
            className={
              isDarkTheme
                ? "rounded-md border border-stone-700 bg-stone-950/60 p-3 text-sm text-stone-300"
                : "rounded-md border border-slate-300 bg-white/85 p-3 text-sm text-slate-700"
            }
          >
            <p
              className={
                isDarkTheme
                  ? "text-xs uppercase tracking-wide text-stone-500"
                  : "text-xs uppercase tracking-wide text-slate-500"
              }
            >
              Vector store
            </p>
            <p className="mt-1">
              {status.data?.vectorStore?.provider ?? "n/a"}
            </p>
          </div>
        </div>
      </Card>

      {selectedTrackId ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm">
          <Card
            className={
              isDarkTheme
                ? "max-h-[92vh] w-full max-w-[1320px] overflow-auto border border-stone-700 bg-stone-900/95"
                : "max-h-[92vh] w-full max-w-[1320px] overflow-auto border border-slate-300 bg-white/95"
            }
          >
            <div
              className={
                isDarkTheme
                  ? "sticky top-0 z-10 flex items-start justify-between gap-4 border-b border-stone-700 bg-stone-900/95 px-4 py-3"
                  : "sticky top-0 z-10 flex items-start justify-between gap-4 border-b border-slate-300 bg-white/95 px-4 py-3"
              }
            >
              <div>
                <CardTitle>Track Investigation</CardTitle>
                <CardDescription>
                  Review the saved observation frames and overlays for this
                  track.
                </CardDescription>
              </div>
              <Button
                size="sm"
                variant="ghost"
                onClick={() => setSelectedTrackId("")}
              >
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
                              variant={
                                selectedObservation === option.key
                                  ? "default"
                                  : "ghost"
                              }
                              onClick={() => setSelectedObservation(option.key)}
                            >
                              {option.label}
                            </Button>
                          ))}
                        </div>

                        <TrackObservationViewer
                          track={track}
                          observationKey={selectedObservation}
                          isDarkTheme={isDarkTheme}
                          operatorTimeZone={operatorTimeZone}
                        />

                        <div className="grid gap-3 xl:grid-cols-[minmax(0,1.3fr)_360px]">
                          <Card
                            className={
                              isDarkTheme
                                ? "space-y-3 border border-stone-700 bg-stone-950/50"
                                : "space-y-3 border border-slate-300 bg-slate-100/70"
                            }
                          >
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
                                onClick={() =>
                                  navigate(
                                    `/live?cameraId=${encodeURIComponent(track.cameraId)}`,
                                  )
                                }
                              >
                                Open Live
                              </Button>
                              <Button
                                size="sm"
                                variant="secondary"
                                onClick={() =>
                                  navigate(createPlaybackSearch(track))
                                }
                              >
                                Open Playback Window
                              </Button>
                            </div>
                            <div
                              className={
                                isDarkTheme
                                  ? "grid gap-2 text-sm text-stone-300"
                                  : "grid gap-2 text-sm text-slate-700"
                              }
                            >
                              <div className="flex items-center justify-between gap-2">
                                <span>Segment start</span>
                                <span>
                                  {track.segmentStartAt
                                    ? formatDateTimeInTimeZone(
                                        track.segmentStartAt,
                                        operatorTimeZone,
                                      )
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
                                <span>Faces found</span>
                                <span>{track.faceCount ?? 0}</span>
                              </div>
                              {track.faceDetail ? (
                                <div className="flex items-start justify-between gap-3">
                                  <span>Face detail</span>
                                  <span className="max-w-[220px] text-right">
                                    {track.faceDetail}
                                  </span>
                                </div>
                              ) : null}
                              <div className="flex items-center justify-between gap-2">
                                <span>Closed</span>
                                <span>{track.closedReason}</span>
                              </div>
                            </div>
                          </Card>

                          <Card
                            className={
                              isDarkTheme
                                ? "space-y-3 border border-stone-700 bg-stone-950/50"
                                : "space-y-3 border border-slate-300 bg-slate-100/70"
                            }
                          >
                            <div>
                              <CardTitle>Saved Movement Points</CardTitle>
                              <CardDescription>
                                First, middle, and last point anchors for this
                                track.
                              </CardDescription>
                            </div>
                            <div
                              className={
                                isDarkTheme
                                  ? "grid gap-2 text-xs text-stone-300"
                                  : "grid gap-2 text-xs text-slate-700"
                              }
                            >
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

                        <Card
                          className={
                            isDarkTheme
                              ? "space-y-3 border border-stone-700 bg-stone-950/50"
                              : "space-y-3 border border-slate-300 bg-slate-100/70"
                          }
                        >
                          <div>
                            <CardTitle>Face Review</CardTitle>
                            <CardDescription>
                              Face crop and alignment preview from the middle
                              observation used for face search.
                            </CardDescription>
                          </div>
                          <div className="grid gap-3 md:grid-cols-2">
                            <FacePreviewCard
                              title="Detected Face"
                              description="Padded face crop kept at a stable aspect when room is available."
                              imageSrc={track.faceDetectedDataUrl}
                              isDarkTheme={isDarkTheme}
                            />
                            <FacePreviewCard
                              title="Aligned Face"
                              description="Alignment preview right before feature extraction."
                              imageSrc={track.faceAlignedDataUrl}
                              isDarkTheme={isDarkTheme}
                            />
                          </div>
                        </Card>
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
