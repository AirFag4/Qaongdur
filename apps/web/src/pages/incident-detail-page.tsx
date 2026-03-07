import { useEffect } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  Badge,
  Card,
  CardDescription,
  CardTitle,
  EmptyState,
  EvidenceClipPanel,
  LoadingState,
} from "@qaongdur/ui";
import { apiClient, queryKeys } from "../lib/api";

const severityTone = {
  low: "stone",
  medium: "amber",
  high: "amber",
  critical: "red",
} as const;

export function IncidentDetailPage() {
  const navigate = useNavigate();
  const params = useParams<{ incidentId: string }>();

  const incidents = useQuery({
    queryKey: queryKeys.incidents,
    queryFn: () => apiClient.listIncidents(),
  });

  const selectedIncidentId = params.incidentId ?? incidents.data?.[0]?.id;
  const incident = useQuery({
    queryKey: queryKeys.incident(selectedIncidentId ?? "none"),
    queryFn: () =>
      selectedIncidentId
        ? apiClient.getIncidentById(selectedIncidentId)
        : Promise.resolve(undefined),
    enabled: Boolean(selectedIncidentId),
  });

  useEffect(() => {
    if (!params.incidentId && incidents.data?.[0]?.id) {
      navigate(`/incidents/${incidents.data[0].id}`, { replace: true });
    }
  }, [incidents.data, navigate, params.incidentId]);

  if (incidents.isLoading || incident.isLoading) {
    return <LoadingState label="Loading incident details..." />;
  }

  if (!incidents.data?.length) {
    return (
      <EmptyState
        title="No incidents yet"
        description="This backend slice is focused on camera onboarding, live view, and playback first."
      />
    );
  }

  if (!incident.data) {
    return (
      <EmptyState
        title="Incident unavailable"
        description="Select another incident once incident workflows are backed by the real API."
      />
    );
  }
  const incidentData = incident.data;

  return (
    <div className="grid gap-3 xl:grid-cols-[320px_minmax(0,1fr)_360px]">
      <Card className="space-y-2">
        <div className="flex items-center justify-between">
          <CardTitle>Incidents</CardTitle>
          <CardDescription>History</CardDescription>
        </div>
        <div className="space-y-2">
          {incidents.data?.map((row) => (
            <button
              key={row.id}
              type="button"
              onClick={() => navigate(`/incidents/${row.id}`)}
              className={`w-full rounded-md border p-2 text-left transition-colors ${
                row.id === incidentData.id
                  ? "border-cyan-700 bg-cyan-950/30"
                  : "border-stone-700 bg-stone-950/60 hover:border-stone-600"
              }`}
            >
              <p className="text-sm font-medium text-stone-100">{row.title}</p>
              <p className="mt-1 font-mono text-[11px] text-stone-500">{row.id}</p>
            </button>
          ))}
        </div>
      </Card>

      <div className="space-y-3">
        <Card className="space-y-2">
          <div className="flex items-start justify-between gap-2">
            <div>
              <CardTitle>{incidentData.title}</CardTitle>
              <CardDescription>{incidentData.summary}</CardDescription>
            </div>
            <Badge tone={severityTone[incidentData.severity]}>{incidentData.severity}</Badge>
          </div>
          <div className="grid gap-2 md:grid-cols-2">
            <div className="rounded-md border border-stone-700 bg-stone-950/60 p-2">
              <p className="text-[11px] uppercase tracking-wide text-stone-500">Owner</p>
              <p className="text-sm text-stone-200">{incidentData.owner}</p>
            </div>
            <div className="rounded-md border border-stone-700 bg-stone-950/60 p-2">
              <p className="text-[11px] uppercase tracking-wide text-stone-500">Status</p>
              <p className="text-sm text-stone-200">{incidentData.status}</p>
            </div>
          </div>
        </Card>

        <Card className="space-y-2">
          <div className="flex items-center justify-between">
            <CardTitle>Timeline</CardTitle>
            <CardDescription>{incidentData.timeline.length} events</CardDescription>
          </div>
          <div className="space-y-2">
            {incidentData.timeline.map((item) => (
              <div key={item.id} className="rounded-md border border-stone-700 bg-stone-950/60 p-2">
                <div className="flex items-center justify-between gap-2">
                  <p className="text-xs font-semibold text-stone-200">{item.action}</p>
                  <p className="font-mono text-[11px] text-stone-500">
                    {new Date(item.happenedAt).toLocaleString()}
                  </p>
                </div>
                <p className="text-xs text-stone-400">{item.actor}</p>
                <p className="mt-1 text-xs text-stone-300">{item.note}</p>
              </div>
            ))}
          </div>
        </Card>
      </div>

      <EvidenceClipPanel clips={incidentData.evidence} />
    </div>
  );
}
