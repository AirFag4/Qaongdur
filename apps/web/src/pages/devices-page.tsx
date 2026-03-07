import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
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
import { Card, CardDescription, CardTitle, HealthStatusBadge, LoadingState } from "@qaongdur/ui";
import { apiClient, queryKeys } from "../lib/api";
import { useOperatorOutlet } from "../app/use-operator-outlet";

export function DevicesPage() {
  const { siteId } = useOperatorOutlet();
  const [sorting, setSorting] = useState<SortingState>([{ id: "health", desc: false }]);
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState("all");

  const devices = useQuery({
    queryKey: queryKeys.devices(siteId),
    queryFn: () => apiClient.listDevices(siteId),
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
