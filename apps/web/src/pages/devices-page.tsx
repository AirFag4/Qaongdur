import { useMemo, useState } from "react";
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
import type { Device } from "@qaongdur/types";
import { Button, Card, CardDescription, CardTitle, HealthStatusBadge, LoadingState } from "@qaongdur/ui";
import { RoleGate } from "../auth/role-gate";
import { apiClient, queryKeys } from "../lib/api";
import { useOperatorOutlet } from "../app/use-operator-outlet";

export function DevicesPage() {
  const { siteId, sites } = useOperatorOutlet();
  const queryClient = useQueryClient();
  const [sorting, setSorting] = useState<SortingState>([{ id: "health", desc: false }]);
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState("all");
  const [cameraActionMessage, setCameraActionMessage] = useState<string | null>(null);
  const [cameraActionError, setCameraActionError] = useState<string | null>(null);
  const [draft, setDraft] = useState({
    name: "",
    zone: "",
    rtspUrl: "",
  });

  const invalidateOperationalQueries = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["cameras"] }),
      queryClient.invalidateQueries({ queryKey: ["devices"] }),
      queryClient.invalidateQueries({ queryKey: ["live-tiles"] }),
      queryClient.invalidateQueries({ queryKey: ["overview"] }),
      queryClient.invalidateQueries({ queryKey: ["playback"] }),
    ]);
  };

  const devices = useQuery({
    queryKey: queryKeys.devices(siteId),
    queryFn: () => apiClient.listDevices(siteId),
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
      });
    },
    onMutate: () => {
      setCameraActionError(null);
      setCameraActionMessage(null);
    },
    onSuccess: async () => {
      setDraft({ name: "", zone: "", rtspUrl: "" });
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
          <div className="grid gap-3 lg:grid-cols-[1fr_1fr_minmax(0,2fr)_auto]">
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
            <div className="flex items-end">
              <Button
                size="sm"
                variant="secondary"
                onClick={() => createCamera.mutate()}
                disabled={
                  createCamera.isPending ||
                  !draft.name.trim() ||
                  !draft.zone.trim() ||
                  !draft.rtspUrl.trim()
                }
              >
                {createCamera.isPending ? "Adding..." : "Add Camera"}
              </Button>
            </div>
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
              Camera {createCamera.data.name} added. Open the Live or Playback page to verify the stream.
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

      <Card className="flex flex-wrap items-end gap-3">
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
      </Card>

      <Card className="space-y-2">
        <div className="flex items-center justify-between">
          <CardTitle>Device Inventory</CardTitle>
          <CardDescription>Dense operations view</CardDescription>
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
                  <tr key={row.id} className="border-t border-stone-800 text-xs">
                    {row.getVisibleCells().map((cell) => (
                      <td key={cell.id} className="px-3 py-2 align-top">
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
    </div>
  );
}
