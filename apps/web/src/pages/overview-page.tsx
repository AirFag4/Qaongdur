import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  AlertRail,
  Card,
  CardDescription,
  CardTitle,
  IncidentSummaryCard,
  LoadingState,
} from "@qaongdur/ui";
import { apiClient, queryKeys } from "../lib/api";
import { useOperatorOutlet } from "../app/use-operator-outlet";

export function OverviewPage() {
  const navigate = useNavigate();
  const { siteId } = useOperatorOutlet();
  const overview = useQuery({
    queryKey: queryKeys.overview(siteId),
    queryFn: () => apiClient.getOverview(siteId),
  });

  if (overview.isLoading || !overview.data) {
    return <LoadingState label="Loading dashboard snapshot..." />;
  }

  return (
    <div className="space-y-3">
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        {overview.data.metrics.map((metric) => (
          <Card key={metric.label} className="space-y-1">
            <CardDescription>{metric.label}</CardDescription>
            <p className="text-2xl font-semibold text-stone-100">{metric.value}</p>
            <p className="text-xs text-cyan-300">{metric.delta}</p>
          </Card>
        ))}
      </div>

      <div className="grid gap-3 xl:grid-cols-[minmax(0,1fr)_380px]">
        <Card className="space-y-3">
          <div className="flex items-center justify-between">
            <CardTitle>Active Incidents</CardTitle>
            <CardDescription>Priority first</CardDescription>
          </div>
          <div className="grid gap-2 md:grid-cols-2">
            {overview.data.activeIncidents.map((incident) => (
              <IncidentSummaryCard
                key={incident.id}
                incident={incident}
                onOpen={(incidentId) => navigate(`/incidents/${incidentId}`)}
              />
            ))}
          </div>
        </Card>
        <AlertRail
          alerts={overview.data.topAlerts}
          onSelect={() => navigate("/alerts")}
        />
      </div>

      <Card className="space-y-2">
        <div className="flex items-center justify-between">
          <CardTitle>Stream Health Distribution</CardTitle>
          <CardDescription>Current camera health buckets</CardDescription>
        </div>
        <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-4">
          {overview.data.streamHealth.map((item) => (
            <div key={item.label} className="rounded-md border border-stone-700 bg-stone-950/60 p-3">
              <p className="text-xs uppercase tracking-wide text-stone-500">{item.label}</p>
              <p className="mt-1 text-xl font-semibold text-stone-100">{item.value}</p>
              <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-stone-800">
                <div
                  className="h-full rounded-full bg-cyan-400"
                  style={{
                    width: `${Math.max(6, Math.min(100, item.value * 4))}%`,
                  }}
                />
              </div>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
