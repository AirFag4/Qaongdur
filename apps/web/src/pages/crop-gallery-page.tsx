import { useMemo, useState } from "react";
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

export function CropGalleryPage() {
  const queryClient = useQueryClient();
  const [sourceId, setSourceId] = useState<string>("");
  const [label, setLabel] = useState<CropTrackFilter["label"]>("all");

  const status = useQuery({
    queryKey: queryKeys.visionStatus,
    queryFn: () => apiClient.getVisionStatus(),
    refetchInterval: (query) =>
      query.state.data?.latestJob?.status === "running" ? 4000 : false,
  });

  const sources = useQuery({
    queryKey: queryKeys.visionSources,
    queryFn: () => apiClient.listVisionSources(),
    refetchInterval:
      status.data?.latestJob?.status === "running" ? 4000 : false,
  });

  const activeFilter = useMemo<CropTrackFilter>(
    () => ({
      sourceId: sourceId || undefined,
      label,
    }),
    [label, sourceId],
  );

  const tracks = useQuery({
    queryKey: queryKeys.cropTracks(JSON.stringify(activeFilter)),
    queryFn: () => apiClient.listCropTracks(activeFilter),
    refetchInterval:
      status.data?.latestJob?.status === "running" ? 4000 : false,
  });

  const runJob = useMutation({
    mutationFn: () =>
      apiClient.runVisionMockJob(sourceId ? [sourceId] : undefined),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: queryKeys.visionStatus }),
        queryClient.invalidateQueries({ queryKey: queryKeys.cropTracks(JSON.stringify(activeFilter)) }),
        queryClient.invalidateQueries({ queryKey: queryKeys.visionSources }),
      ]);
    },
  });

  if (sources.isLoading || status.isLoading || tracks.isLoading) {
    return <LoadingState label="Loading crop gallery..." />;
  }

  if (sources.error || status.error || tracks.error) {
    return (
      <EmptyState
        title="Crop gallery unavailable"
        description="Start the vision profile and rerun the mock-video job to populate track crops."
      />
    );
  }

  return (
    <div className="space-y-3">
      <FilterBar>
        <FilterField label="Source">
          <select
            className="form-input"
            value={sourceId}
            onChange={(event) => setSourceId(event.target.value)}
          >
            <option value="">All sources</option>
            {sources.data?.map((source) => (
              <option key={source.id} value={source.id}>
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
        <RoleGate anyOf={["site-admin", "platform-admin"]}>
          <Button
            size="sm"
            variant="secondary"
            disabled={runJob.isPending || status.data?.latestJob?.status === "running"}
            onClick={() => runJob.mutate()}
          >
            {status.data?.latestJob?.status === "running" ? "Processing..." : "Run Mock Videos"}
          </Button>
        </RoleGate>
      </FilterBar>

      <div className="grid gap-3 xl:grid-cols-[minmax(0,1fr)_360px]">
        <Card className="space-y-3">
          <div className="flex items-center justify-between gap-3">
            <div>
              <CardTitle>Crop Tracks</CardTitle>
              <CardDescription>
                Representative middle crops for tracked people and vehicles, with first and last sighting metadata below.
              </CardDescription>
            </div>
            <div className="text-right text-xs text-stone-400">
              <p>{tracks.data?.length ?? 0} tracks</p>
              <p>Detector: {status.data?.detector.modelName}</p>
            </div>
          </div>

          {!tracks.data?.length ? (
            <EmptyState
              title="No crop tracks yet"
              description="Run the mock-video pipeline to generate tracked crop cards."
            />
          ) : (
            <div className="grid auto-rows-fr gap-3 md:grid-cols-2 2xl:grid-cols-3">
              {tracks.data.map((track) => (
                <Card key={track.id} className="flex h-full flex-col gap-3">
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

                  <div className="space-y-1">
                    <div className="aspect-[4/5] overflow-hidden rounded-md border border-stone-700 bg-stone-950">
                      <img
                        src={track.middleCropDataUrl}
                        alt={`${track.cameraName} representative crop`}
                        className="h-full w-full object-cover"
                      />
                    </div>
                    <p className="text-center text-[11px] text-stone-500">Representative crop</p>
                  </div>

                  <div className="grid gap-2 text-[11px] text-stone-400 sm:grid-cols-2">
                    <div>
                      <p className="text-stone-500">First seen</p>
                      <p>{track.firstSeenOffsetLabel}</p>
                    </div>
                    <div>
                      <p className="text-stone-500">Main frame</p>
                      <p>{track.middleSeenOffsetLabel}</p>
                    </div>
                    <div>
                      <p className="text-stone-500">Last seen</p>
                      <p>{track.lastSeenOffsetLabel}</p>
                    </div>
                    <div>
                      <p className="text-stone-500">Frames</p>
                      <p>
                        {track.frameCount} @ {track.sampleFps} fps
                      </p>
                    </div>
                    <div>
                      <p className="text-stone-500">Embedding</p>
                      <p>
                        {track.embeddingStatus}
                        {track.embeddingModel ? ` • ${track.embeddingModel}` : ""}
                      </p>
                    </div>
                    <div>
                      <p className="text-stone-500">Face stage</p>
                      <p>
                        {track.faceStatus}
                        {track.faceModel ? ` • ${track.faceModel}` : ""}
                      </p>
                    </div>
                  </div>
                </Card>
              ))}
            </div>
          )}
        </Card>

        <Card className="space-y-3">
          <div>
            <CardTitle>Vision Status</CardTitle>
              <CardDescription>
              VMS-backed mock-video processing status, storage usage, and runtime model selection.
            </CardDescription>
          </div>

          <div className="space-y-2 rounded-md border border-stone-700 bg-stone-950/60 p-3 text-sm text-stone-300">
            <div className="flex items-center justify-between gap-2">
              <span>Latest job</span>
              <span>{status.data?.latestJob?.status ?? "idle"}</span>
            </div>
            <div className="flex items-center justify-between gap-2">
              <span>Tracks stored</span>
              <span>{status.data?.latestJob?.trackCount ?? 0}</span>
            </div>
            <div className="flex items-center justify-between gap-2">
              <span>Storage used</span>
              <span>{formatBytes(status.data?.storage.usedBytes ?? 0)}</span>
            </div>
            <div className="flex items-center justify-between gap-2">
              <span>Storage budget</span>
              <span>{formatBytes(status.data?.storage.limitBytes ?? 0)}</span>
            </div>
            <div className="flex items-center justify-between gap-2">
              <span>Detector</span>
              <span>{status.data?.detector.modelName}</span>
            </div>
            <div className="flex items-center justify-between gap-2">
              <span>Embedding</span>
              <span>{status.data?.embedding.modelName}</span>
            </div>
            <div className="flex items-center justify-between gap-2">
              <span>Face</span>
              <span>{status.data?.face.modelName}</span>
            </div>
            <div className="flex items-center justify-between gap-2">
              <span>Face mode</span>
              <span>{status.data?.face.mode}</span>
            </div>
            <div className="rounded-md border border-stone-800 bg-stone-900/70 p-2 text-[11px] text-stone-400">
              {status.data?.face.detail}
            </div>
            {status.data?.latestJob?.detail ? (
              <div className="rounded border border-amber-700/70 bg-amber-950/40 px-2 py-1 text-xs text-amber-200">
                {status.data.latestJob.detail}
              </div>
            ) : null}
          </div>

          <div className="rounded-md border border-dashed border-stone-700 bg-stone-950/50 p-3 text-xs text-stone-400">
            ROI filtering is not implemented in this page yet. The current Task 03 plan keeps ROI as a future database design item so the track schema can evolve without rewriting the gallery contract.
          </div>
        </Card>
      </div>
    </div>
  );
}
