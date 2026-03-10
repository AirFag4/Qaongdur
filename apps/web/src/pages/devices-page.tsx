import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  type ColumnDef,
  type SortingState,
  flexRender,
  getCoreRowModel,
  getFilteredRowModel,
  getSortedRowModel,
  useReactTable,
} from "@tanstack/react-table";
import type { Device, RtspTransport } from "@qaongdur/types";
import { Button, Card, CardDescription, CardTitle, EmptyState, HealthStatusBadge, LoadingState } from "@qaongdur/ui";
import { useNavigate } from "react-router-dom";
import { RoleGate } from "../auth/role-gate";
import { DeviceMap } from "../components/device-map";
import { apiClient, queryKeys } from "../lib/api";
import { createRecentAbsoluteRange } from "../lib/bkk-time";
import { useOperatorOutlet } from "../app/use-operator-outlet";

type CameraDraft = {
  name: string;
  zone: string;
  rtspUrl: string;
  latitude: string;
  longitude: string;
  heading: string;
  locationNote: string;
  rtspTransport: RtspTransport;
  rtspAnyPort: boolean;
};

const toOptionalNumber = (value: string) => {
  const trimmed = value.trim();
  if (!trimmed) {
    return undefined;
  }
  const parsed = Number(trimmed);
  return Number.isFinite(parsed) ? parsed : undefined;
};

const formatCoordinate = (value?: number | null) =>
  typeof value === "number" ? value.toFixed(6) : "Unmapped";

const buildPlaybackQuery = (cameraId: string) => {
  const { from, to } = createRecentAbsoluteRange();
  return new URLSearchParams({
    cameraId,
    from: from.toISOString(),
    to: to.toISOString(),
  }).toString();
};

export function DevicesPage() {
  const navigate = useNavigate();
  const { siteId, sites, themeMode } = useOperatorOutlet();
  const queryClient = useQueryClient();
  const [sorting, setSorting] = useState<SortingState>([{ id: "health", desc: false }]);
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState("all");
  const [viewMode, setViewMode] = useState<"inventory" | "map">("inventory");
  const [selectedCameraId, setSelectedCameraId] = useState<string>();
  const [cameraActionMessage, setCameraActionMessage] = useState<string | null>(null);
  const [cameraActionError, setCameraActionError] = useState<string | null>(null);
  const [draft, setDraft] = useState<CameraDraft>({
    name: "",
    zone: "",
    rtspUrl: "",
    latitude: "",
    longitude: "",
    heading: "",
    locationNote: "",
    rtspTransport: "automatic",
    rtspAnyPort: false,
  });

  const invalidateOperationalQueries = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["cameras"] }),
      queryClient.invalidateQueries({ queryKey: ["devices"] }),
      queryClient.invalidateQueries({ queryKey: ["live-tiles"] }),
      queryClient.invalidateQueries({ queryKey: ["overview"] }),
      queryClient.invalidateQueries({ queryKey: ["playback"] }),
      queryClient.invalidateQueries({ queryKey: ["device-map"] }),
    ]);
  };

  const devices = useQuery({
    queryKey: queryKeys.devices(siteId),
    queryFn: () => apiClient.listDevices(siteId),
  });
  const deviceMap = useQuery({
    queryKey: queryKeys.deviceMap(siteId),
    queryFn: () => apiClient.listDeviceMapCameras(siteId),
  });

  const createCamera = useMutation({
    mutationFn: async () => {
      const targetSiteId = siteId ?? sites[0]?.id;
      if (!targetSiteId) {
        throw new Error("No site is available for camera onboarding.");
      }

        return apiClient.createCamera({
          siteId: targetSiteId,
          name: draft.name.trim(),
          zone: draft.zone.trim(),
          rtspUrl: draft.rtspUrl.trim(),
          latitude: toOptionalNumber(draft.latitude),
          longitude: toOptionalNumber(draft.longitude),
          heading: toOptionalNumber(draft.heading),
          locationNote: draft.locationNote.trim() || undefined,
          rtspTransport: draft.rtspTransport,
          rtspAnyPort: draft.rtspAnyPort,
        });
    },
    onMutate: () => {
      setCameraActionError(null);
      setCameraActionMessage(null);
    },
    onSuccess: async () => {
      setDraft({
        name: "",
        zone: "",
        rtspUrl: "",
        latitude: "",
        longitude: "",
        heading: "",
        locationNote: "",
        rtspTransport: "automatic",
        rtspAnyPort: false,
      });
      await invalidateOperationalQueries();
    },
  });

  const reconnectCamera = useMutation({
    mutationFn: async (camera: { cameraId: string; name: string }) =>
      apiClient.reconnectCamera(camera.cameraId),
    onMutate: () => {
      setCameraActionError(null);
      setCameraActionMessage(null);
    },
    onSuccess: async (_camera, variables) => {
      setCameraActionMessage(`Reconnect requested for ${variables.name}.`);
      await invalidateOperationalQueries();
    },
    onError: (error, variables) => {
      setCameraActionError(
        error instanceof Error
          ? error.message
          : `Reconnect failed for ${variables.name}.`,
      );
    },
  });

  const deleteCamera = useMutation({
    mutationFn: async (camera: { cameraId: string; name: string }) => {
      await apiClient.deleteCamera(camera.cameraId);
      return camera;
    },
    onMutate: () => {
      setCameraActionError(null);
      setCameraActionMessage(null);
    },
    onSuccess: async (camera) => {
      setCameraActionMessage(`Camera ${camera.name} removed.`);
      await invalidateOperationalQueries();
    },
    onError: (error, variables) => {
      setCameraActionError(
        error instanceof Error
          ? error.message
          : `Remove failed for ${variables.name}.`,
      );
    },
  });

  const filteredDevices = useMemo(() => {
    const text = search.toLowerCase();
    return (devices.data ?? []).filter((device) => {
      if (typeFilter !== "all" && device.type !== typeFilter) {
        return false;
      }
      if (!text) {
        return true;
      }
      return `${device.name} ${device.model} ${device.ipAddress}`
        .toLowerCase()
        .includes(text);
    });
  }, [devices.data, search, typeFilter]);

  useEffect(() => {
    if (!deviceMap.data?.length) {
      setSelectedCameraId(undefined);
      return;
    }

    if (selectedCameraId && deviceMap.data.some((camera) => camera.cameraId === selectedCameraId)) {
      return;
    }

    setSelectedCameraId(deviceMap.data[0].cameraId);
  }, [deviceMap.data, selectedCameraId]);

  const selectedMapCamera = useMemo(
    () =>
      deviceMap.data?.find((camera) => camera.cameraId === selectedCameraId) ??
      deviceMap.data?.[0],
    [deviceMap.data, selectedCameraId],
  );
  const selectedDevice = useMemo(
    () =>
      filteredDevices.find((device) => device.cameraId === selectedMapCamera?.cameraId) ??
      devices.data?.find((device) => device.cameraId === selectedMapCamera?.cameraId),
    [devices.data, filteredDevices, selectedMapCamera?.cameraId],
  );
  const hasLocationPair =
    Boolean(draft.latitude.trim()) === Boolean(draft.longitude.trim());

  const columns = useMemo<ColumnDef<Device>[]>(
    () => [
      {
        accessorKey: "name",
        header: "Device",
        cell: ({ row }) => (
          <div>
            <p className="text-xs font-medium text-stone-100">{row.original.name}</p>
            <p className="text-[11px] text-stone-500">{row.original.model}</p>
          </div>
        ),
      },
      {
        accessorKey: "type",
        header: "Type",
      },
      {
        accessorKey: "ipAddress",
        header: "IP",
        cell: ({ row }) => (
          <span className="font-mono text-[11px] text-stone-300">{row.original.ipAddress}</span>
        ),
      },
      {
        id: "location",
        header: "Location",
        cell: ({ row }) =>
          row.original.latitude != null && row.original.longitude != null ? (
            <div>
              <p className="text-[11px] text-[var(--qa-panel-text)]">
                {formatCoordinate(row.original.latitude)}, {formatCoordinate(row.original.longitude)}
              </p>
              {row.original.locationNote ? (
                <p className="text-[11px] text-[var(--qa-panel-text-subtle)]">
                  {row.original.locationNote}
                </p>
              ) : null}
            </div>
          ) : (
            <span className="text-[11px] text-[var(--qa-panel-text-subtle)]">Unmapped</span>
          ),
      },
      {
        accessorKey: "health",
        header: "Health",
        cell: ({ row }) => <HealthStatusBadge status={row.original.health} />,
      },
      {
        accessorKey: "uptimePct",
        header: "Uptime",
        cell: ({ row }) => <span className="text-xs">{row.original.uptimePct.toFixed(2)}%</span>,
      },
      {
        id: "actions",
        header: "Actions",
        cell: ({ row }) => {
          const cameraId = row.original.cameraId;
          if (row.original.type !== "camera" || !cameraId) {
            return <span className="text-[11px] text-stone-600">-</span>;
          }
          if (row.original.tags.includes("system-managed")) {
            return <span className="text-[11px] text-stone-500">System managed</span>;
          }

          const reconnectPending =
            reconnectCamera.isPending &&
            reconnectCamera.variables?.cameraId === cameraId;
          const deletePending =
            deleteCamera.isPending &&
            deleteCamera.variables?.cameraId === cameraId;

          return (
            <RoleGate
              anyOf={["site-admin", "platform-admin"]}
              fallback={<span className="text-[11px] text-stone-600">Admin only</span>}
            >
              <div className="flex flex-wrap gap-2">
                <Button
                  type="button"
                  size="sm"
                  variant="ghost"
                  disabled={reconnectPending || deletePending}
                  onClick={() =>
                    reconnectCamera.mutate({
                      cameraId,
                      name: row.original.name,
                    })
                  }
                >
                  {reconnectPending ? "Reconnecting..." : "Reconnect"}
                </Button>
                <Button
                  type="button"
                  size="sm"
                  variant="ghost"
                  className="text-red-300 hover:bg-red-950/50 hover:text-red-200"
                  disabled={reconnectPending || deletePending}
                  onClick={() => {
                    if (
                      !window.confirm(
                        `Remove camera ${row.original.name}? This stops live relay and removes it from the inventory.`,
                      )
                    ) {
                      return;
                    }

                    deleteCamera.mutate({
                      cameraId,
                      name: row.original.name,
                    });
                  }}
                >
                  {deletePending ? "Removing..." : "Remove"}
                </Button>
              </div>
            </RoleGate>
          );
        },
      },
    ],
    [deleteCamera, reconnectCamera],
  );

  const table = useReactTable({
    data: filteredDevices,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
  });

  const geolocatedCameraCount = deviceMap.data?.length ?? 0;
  const totalCameraCount = (devices.data ?? []).filter((device) => device.type === "camera").length;
  const selectedDetail = selectedMapCamera && selectedDevice
    ? { camera: selectedMapCamera, device: selectedDevice }
    : null;

  return (
    <div className="space-y-3">
      <RoleGate
        anyOf={["site-admin", "platform-admin"]}
        fallback={
          <Card className="space-y-2">
            <CardTitle>Camera Onboarding</CardTitle>
            <CardDescription>
              Site administrators and platform administrators can add RTSP cameras.
            </CardDescription>
          </Card>
        }
      >
        <Card className="space-y-3">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <CardTitle>Add RTSP Camera</CardTitle>
              <CardDescription>
                The camera will be proxied through MediaMTX for live HLS viewing and recorded
                for playback search.
              </CardDescription>
            </div>
            <div className="rounded-md border border-stone-800 bg-stone-950/60 px-3 py-2 text-[11px] text-stone-400">
              Target site: {sites.find((site) => site.id === (siteId ?? sites[0]?.id))?.name ?? "Unavailable"}
            </div>
          </div>
          <div className="grid gap-3 lg:grid-cols-[1fr_1fr_minmax(0,2fr)_160px_160px]">
            <label className="flex flex-col gap-1 text-xs text-stone-400">
              Camera name
              <input
                className="form-input"
                value={draft.name}
                onChange={(event) =>
                  setDraft((previous) => ({ ...previous, name: event.target.value }))
                }
                placeholder="North Gate Camera"
              />
            </label>
            <label className="flex flex-col gap-1 text-xs text-stone-400">
              Zone
              <input
                className="form-input"
                value={draft.zone}
                onChange={(event) =>
                  setDraft((previous) => ({ ...previous, zone: event.target.value }))
                }
                placeholder="North Gate"
              />
            </label>
            <label className="flex flex-col gap-1 text-xs text-stone-400">
              RTSP URL
              <input
                className="form-input font-mono text-[11px]"
                value={draft.rtspUrl}
                onChange={(event) =>
                  setDraft((previous) => ({ ...previous, rtspUrl: event.target.value }))
                }
                placeholder="rtsp://user:pass@camera-host:554/stream"
              />
            </label>
            <label className="flex flex-col gap-1 text-xs text-stone-400">
              RTSP transport
              <select
                className="form-select"
                value={draft.rtspTransport}
                onChange={(event) =>
                  setDraft((previous) => ({
                    ...previous,
                    rtspTransport: event.target.value as RtspTransport,
                  }))
                }
              >
                <option value="automatic">Automatic</option>
                <option value="udp">UDP</option>
                <option value="tcp">TCP</option>
                <option value="multicast">Multicast</option>
              </select>
            </label>
            <div className="flex items-end">
              <Button
                size="sm"
                variant="secondary"
                onClick={() => createCamera.mutate()}
                disabled={
                  createCamera.isPending ||
                  !draft.name.trim() ||
                  !draft.zone.trim() ||
                  !draft.rtspUrl.trim() ||
                  !hasLocationPair
                }
              >
                {createCamera.isPending ? "Adding..." : "Add Camera"}
              </Button>
            </div>
          </div>
          <div className="grid gap-3 lg:grid-cols-[140px_140px_140px_minmax(0,1fr)]">
            <label className="flex flex-col gap-1 text-xs text-stone-400">
              Latitude
              <input
                className="form-input"
                type="number"
                step="any"
                value={draft.latitude}
                onChange={(event) =>
                  setDraft((previous) => ({ ...previous, latitude: event.target.value }))
                }
                placeholder="13.756300"
              />
            </label>
            <label className="flex flex-col gap-1 text-xs text-stone-400">
              Longitude
              <input
                className="form-input"
                type="number"
                step="any"
                value={draft.longitude}
                onChange={(event) =>
                  setDraft((previous) => ({ ...previous, longitude: event.target.value }))
                }
                placeholder="100.501800"
              />
            </label>
            <label className="flex flex-col gap-1 text-xs text-stone-400">
              Heading
              <input
                className="form-input"
                type="number"
                step="any"
                value={draft.heading}
                onChange={(event) =>
                  setDraft((previous) => ({ ...previous, heading: event.target.value }))
                }
                placeholder="90"
              />
            </label>
            <label className="flex flex-col gap-1 text-xs text-stone-400">
              Location note
              <input
                className="form-input"
                value={draft.locationNote}
                onChange={(event) =>
                  setDraft((previous) => ({ ...previous, locationNote: event.target.value }))
                }
                placeholder="Gate pole facing westbound lanes"
              />
            </label>
          </div>
          <div className="flex flex-wrap items-center gap-4 text-xs text-stone-400">
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                className="h-4 w-4 rounded border-stone-700 bg-stone-950 text-cyan-400"
                checked={draft.rtspAnyPort}
                onChange={(event) =>
                  setDraft((previous) => ({
                    ...previous,
                    rtspAnyPort: event.target.checked,
                  }))
                }
              />
              Enable MediaMTX `rtspAnyPort` compatibility mode
            </label>
            <p className="text-[11px] text-stone-500">
              Automatic is the default. If VLC works but MediaMTX fails after SDP or TCP
              negotiation, try `udp`. Enable `rtspAnyPort` only for cameras that need relaxed
              UDP port handling.
            </p>
            {!hasLocationPair ? (
              <p className="text-[11px] text-amber-300">
                Latitude and longitude must be provided together.
              </p>
            ) : null}
          </div>
          {createCamera.error ? (
            <p className="text-xs text-red-300">
              {createCamera.error instanceof Error
                ? createCamera.error.message
                : "Camera onboarding failed."}
            </p>
          ) : null}
          {createCamera.data ? (
            <p className="text-xs text-emerald-300">
              Camera {createCamera.data.name} added with {createCamera.data.rtspTransport ?? "automatic"} RTSP transport.
              Open the Live or Playback page to verify the stream.
            </p>
          ) : null}
        </Card>
      </RoleGate>

      {cameraActionError ? (
        <Card className="border border-red-500/30 bg-red-950/20">
          <p className="text-xs text-red-200">{cameraActionError}</p>
        </Card>
      ) : null}

      {cameraActionMessage ? (
        <Card className="border border-emerald-500/30 bg-emerald-950/20">
          <p className="text-xs text-emerald-200">{cameraActionMessage}</p>
        </Card>
      ) : null}

      <Card className="flex flex-wrap items-end justify-between gap-3">
        <div className="flex flex-wrap items-end gap-3">
          <label className="flex min-w-52 flex-col gap-1 text-xs text-stone-400">
          Search
          <input
            className="form-input"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Device/model/IP..."
          />
          </label>
          <label className="flex min-w-40 flex-col gap-1 text-xs text-stone-400">
          Type
          <select
            className="form-select"
            value={typeFilter}
            onChange={(event) => setTypeFilter(event.target.value)}
          >
            <option value="all">All</option>
            <option value="camera">Camera</option>
            <option value="nvr">NVR</option>
            <option value="gateway">Gateway</option>
            <option value="sensor">Sensor</option>
          </select>
          </label>
        </div>
        <div className="flex flex-col items-end gap-2">
          <div className="flex items-center gap-2">
            <Button
              size="sm"
              variant={viewMode === "inventory" ? "default" : "ghost"}
              onClick={() => setViewMode("inventory")}
            >
              Inventory
            </Button>
            <Button
              size="sm"
              variant={viewMode === "map" ? "default" : "ghost"}
              onClick={() => setViewMode("map")}
            >
              Device Map
            </Button>
          </div>
          <p className="text-[11px] text-[var(--qa-panel-text-subtle)]">
            {geolocatedCameraCount}/{totalCameraCount} cameras mapped
          </p>
        </div>
      </Card>

      {viewMode === "inventory" ? (
        <Card className="space-y-2">
          <div className="flex items-center justify-between">
            <CardTitle>Device Inventory</CardTitle>
            <CardDescription>Dense operations view with geolocation status</CardDescription>
          </div>
          {devices.isLoading ? (
            <LoadingState label="Loading device inventory..." />
          ) : (
            <div className="overflow-auto rounded-lg border border-stone-700">
              <table className="min-w-full text-left">
                <thead className="bg-stone-950/80">
                  {table.getHeaderGroups().map((headerGroup) => (
                    <tr key={headerGroup.id}>
                      {headerGroup.headers.map((header) => (
                        <th
                          key={header.id}
                          className="px-3 py-2 text-[11px] font-semibold uppercase tracking-wide text-stone-500"
                        >
                          {header.isPlaceholder ? null : (
                            <button
                              type="button"
                              className="flex items-center gap-1"
                              onClick={header.column.getToggleSortingHandler()}
                            >
                              {flexRender(
                                header.column.columnDef.header,
                                header.getContext(),
                              )}
                              {{
                                asc: "↑",
                                desc: "↓",
                              }[header.column.getIsSorted() as string] ?? null}
                            </button>
                          )}
                        </th>
                      ))}
                    </tr>
                  ))}
                </thead>
                <tbody>
                  {table.getRowModel().rows.map((row) => (
                    <tr
                      key={row.id}
                      className={`border-t border-stone-800 text-xs ${
                        row.original.cameraId && row.original.cameraId === selectedCameraId
                          ? "bg-cyan-950/20"
                          : ""
                      }`}
                    >
                      {row.getVisibleCells().map((cell) => (
                        <td
                          key={cell.id}
                          className="px-3 py-2 align-top"
                          onClick={() => {
                            if (row.original.cameraId) {
                              setSelectedCameraId(row.original.cameraId);
                            }
                          }}
                        >
                          {flexRender(cell.column.columnDef.cell, cell.getContext())}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      ) : (
        <div className="grid gap-3 xl:grid-cols-[minmax(0,1.4fr)_380px]">
          <Card className="space-y-3">
            <div className="flex items-center justify-between gap-3">
              <div>
                <CardTitle>Device Map</CardTitle>
                <CardDescription>
                  MapLibre-backed view of geolocated cameras with direct investigation pivots.
                </CardDescription>
              </div>
              <p className="text-[11px] text-[var(--qa-panel-text-subtle)]">
                OpenStreetMap raster tiles
              </p>
            </div>
            {deviceMap.isLoading ? (
              <LoadingState label="Loading mapped cameras..." />
            ) : (
              <DeviceMap
                cameras={deviceMap.data ?? []}
                selectedCameraId={selectedCameraId}
                onSelectCamera={setSelectedCameraId}
                themeMode={themeMode}
              />
            )}
          </Card>

          <Card className="space-y-3">
            <div>
              <CardTitle>Camera Detail</CardTitle>
              <CardDescription>
                Inspect mapped camera metadata, then pivot into live, playback, or crops.
              </CardDescription>
            </div>
            {!selectedDetail ? (
              <EmptyState
                title="No camera selected"
                description="Pick a mapped camera marker to inspect its coordinates and investigation pivots."
              />
            ) : (
              <>
                <div className="space-y-2 rounded-lg border border-[var(--qa-panel-border)] bg-[var(--qa-panel-muted-bg)] p-3">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="text-sm font-semibold text-[var(--qa-card-title)]">
                        {selectedDetail.camera.name}
                      </p>
                      <p className="text-xs text-[var(--qa-panel-text-muted)]">
                        {selectedDetail.camera.zone}
                      </p>
                    </div>
                    <HealthStatusBadge status={selectedDetail.camera.health} />
                  </div>
                  <div className="grid gap-2 text-xs text-[var(--qa-panel-text-muted)]">
                    <div className="flex items-center justify-between gap-2">
                      <span>Latitude</span>
                      <span>{formatCoordinate(selectedDetail.camera.latitude)}</span>
                    </div>
                    <div className="flex items-center justify-between gap-2">
                      <span>Longitude</span>
                      <span>{formatCoordinate(selectedDetail.camera.longitude)}</span>
                    </div>
                    <div className="flex items-center justify-between gap-2">
                      <span>Heading</span>
                      <span>
                        {selectedDetail.camera.heading != null
                          ? `${selectedDetail.camera.heading.toFixed(0)} deg`
                          : "Unset"}
                      </span>
                    </div>
                    <div className="flex items-center justify-between gap-2">
                      <span>Source</span>
                      <span>
                        {selectedDetail.camera.isSystemManaged ? "System-managed" : "Manual RTSP"}
                      </span>
                    </div>
                    <div className="flex items-center justify-between gap-2">
                      <span>IP</span>
                      <span className="font-mono">{selectedDetail.device.ipAddress}</span>
                    </div>
                  </div>
                  {selectedDetail.camera.locationNote ? (
                    <div className="rounded-md border border-[var(--qa-panel-border)] bg-[var(--qa-panel-subtle-bg)] px-3 py-2 text-xs text-[var(--qa-panel-text)]">
                      {selectedDetail.camera.locationNote}
                    </div>
                  ) : null}
                </div>

                <div className="flex flex-wrap gap-2">
                  <Button
                    size="sm"
                    variant="secondary"
                    onClick={() =>
                      navigate(`/live?cameraId=${encodeURIComponent(selectedDetail.camera.cameraId)}`)
                    }
                  >
                    Open Live
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() =>
                      navigate(
                        `/playback?${buildPlaybackQuery(selectedDetail.camera.cameraId)}`,
                      )
                    }
                  >
                    Open Playback
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() =>
                      navigate(`/crops?cameraId=${encodeURIComponent(selectedDetail.camera.cameraId)}`)
                    }
                  >
                    Open Crops
                  </Button>
                </div>
              </>
            )}
          </Card>
        </div>
      )}
    </div>
  );
}
