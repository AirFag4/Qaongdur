import { useMemo, useState } from "react";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { useQuery } from "@tanstack/react-query";
import {
  type ColumnDef,
  type SortingState,
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  useReactTable,
} from "@tanstack/react-table";
import type { AlertEvent } from "@qaongdur/types";
import {
  Badge,
  Button,
  Card,
  CardTitle,
  FilterBar,
  FilterField,
  LoadingState,
} from "@qaongdur/ui";
import { apiClient, queryKeys } from "../lib/api";
import { useOperatorOutlet } from "../app/use-operator-outlet";

const alertFilterSchema = z.object({
  severity: z.enum(["all", "low", "medium", "high", "critical"]),
  status: z.enum(["all", "new", "acknowledged", "investigating", "resolved"]),
  search: z.string().max(120),
});

type AlertFilterForm = z.infer<typeof alertFilterSchema>;

const severityTone = {
  low: "stone",
  medium: "amber",
  high: "amber",
  critical: "red",
} as const;

export function AlertsEventsPage() {
  const { siteId, cameras } = useOperatorOutlet();
  const [sorting, setSorting] = useState<SortingState>([
    { id: "happenedAt", desc: true },
  ]);
  const [activeFilter, setActiveFilter] = useState<AlertFilterForm>({
    severity: "all",
    status: "all",
    search: "",
  });

  const form = useForm<AlertFilterForm>({
    resolver: zodResolver(alertFilterSchema),
    defaultValues: activeFilter,
  });

  const alerts = useQuery({
    queryKey: queryKeys.alerts({ ...activeFilter, siteId }),
    queryFn: () =>
      apiClient.listAlerts({
        siteId,
        severity: activeFilter.severity,
        status: activeFilter.status,
        search: activeFilter.search,
      }),
  });

  const cameraNameById = useMemo(
    () => new Map(cameras.map((camera) => [camera.id, camera.name])),
    [cameras],
  );

  const columns = useMemo<ColumnDef<AlertEvent>[]>(
    () => [
      {
        accessorKey: "happenedAt",
        header: "Time",
        cell: ({ row }) => (
          <span className="font-mono text-[11px] text-stone-400">
            {new Date(row.original.happenedAt).toLocaleString()}
          </span>
        ),
      },
      {
        accessorKey: "severity",
        header: "Severity",
        cell: ({ row }) => (
          <Badge tone={severityTone[row.original.severity]}>{row.original.severity}</Badge>
        ),
      },
      {
        accessorKey: "title",
        header: "Title",
        cell: ({ row }) => (
          <div>
            <p className="text-xs font-medium text-stone-100">{row.original.title}</p>
            <p className="text-[11px] text-stone-400">{row.original.summary}</p>
          </div>
        ),
      },
      {
        id: "camera",
        header: "Camera",
        cell: ({ row }) => (
          <span className="text-xs text-stone-300">
            {cameraNameById.get(row.original.cameraId) ?? row.original.cameraId}
          </span>
        ),
      },
      {
        accessorKey: "status",
        header: "Status",
        cell: ({ row }) => (
          <span className="text-xs uppercase tracking-wide text-stone-400">
            {row.original.status}
          </span>
        ),
      },
    ],
    [cameraNameById],
  );

  const table = useReactTable({
    data: alerts.data ?? [],
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  });

  return (
    <div className="space-y-3">
      <FilterBar onReset={() => {
        const resetValues: AlertFilterForm = { severity: "all", status: "all", search: "" };
        form.reset(resetValues);
        setActiveFilter(resetValues);
      }}>
        <FilterField label="Severity">
          <select
            className="form-select"
            {...form.register("severity")}
          >
            <option value="all">All</option>
            <option value="low">Low</option>
            <option value="medium">Medium</option>
            <option value="high">High</option>
            <option value="critical">Critical</option>
          </select>
        </FilterField>
        <FilterField label="Status">
          <select
            className="form-select"
            {...form.register("status")}
          >
            <option value="all">All</option>
            <option value="new">New</option>
            <option value="acknowledged">Acknowledged</option>
            <option value="investigating">Investigating</option>
            <option value="resolved">Resolved</option>
          </select>
        </FilterField>
        <FilterField label="Search">
          <input
            className="form-input"
            placeholder="Rule, title, summary..."
            {...form.register("search")}
          />
        </FilterField>
        <Button
          size="sm"
          variant="secondary"
          onClick={form.handleSubmit((values: AlertFilterForm) => setActiveFilter(values))}
        >
          Apply
        </Button>
      </FilterBar>

      <Card className="space-y-2">
        <CardTitle>Alerts & Events</CardTitle>
        {alerts.isLoading ? (
          <LoadingState label="Loading alerts..." />
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
