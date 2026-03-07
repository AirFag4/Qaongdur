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
  const [draft, setDraft] = useState({
    name: "",
    zone: "",
    rtspUrl: "",
  });

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
    onSuccess: async () => {
      setDraft({ name: "", zone: "", rtspUrl: "" });
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["cameras"] }),
        queryClient.invalidateQueries({ queryKey: ["devices"] }),
        queryClient.invalidateQueries({ queryKey: ["live-tiles"] }),
        queryClient.invalidateQueries({ queryKey: ["overview"] }),
        queryClient.invalidateQueries({ queryKey: ["playback"] }),
      ]);
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
    ],
    [],
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
