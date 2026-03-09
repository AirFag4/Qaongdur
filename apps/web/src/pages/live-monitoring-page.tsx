import { useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { AlertRail, Button, CameraGrid, Card, CardDescription, CardTitle, LoadingState } from "@qaongdur/ui";
import { useSearchParams } from "react-router-dom";
import { apiClient, queryKeys } from "../lib/api";
import { useOperatorOutlet } from "../app/use-operator-outlet";

const gridOptions = [1, 4, 9, 16] as const;

export function LiveMonitoringPage() {
  const { siteId, cameras, selectedCameraIds, liveGridSize, setLiveGridSize, setSelectedCameraIds } =
    useOperatorOutlet();
  const [searchParams] = useSearchParams();
  const cameraIdParam = searchParams.get("cameraId");

  const liveTiles = useQuery({
    queryKey: queryKeys.liveTiles(siteId),
    queryFn: () => apiClient.listLiveTiles(siteId),
  });
  const alerts = useQuery({
    queryKey: queryKeys.alerts({ siteId, status: "new" }),
    queryFn: () => apiClient.listAlerts({ siteId, status: "new" }),
  });

  useEffect(() => {
    if (!cameraIdParam) {
      return;
    }
    const cameraExists = cameras.some((camera) => camera.id === cameraIdParam);
    if (!cameraExists) {
      return;
    }
    if (selectedCameraIds.length === 1 && selectedCameraIds[0] === cameraIdParam) {
      return;
    }
    setSelectedCameraIds([cameraIdParam]);
  }, [cameraIdParam, cameras, selectedCameraIds, setSelectedCameraIds]);

  if (liveTiles.isLoading || !liveTiles.data) {
    return <LoadingState label="Loading live camera streams..." />;
  }

  const selectedSet = new Set(selectedCameraIds);
  const scopedCameras = selectedSet.size
    ? cameras.filter((camera) => selectedSet.has(camera.id))
    : cameras;

  return (
    <div className="space-y-3">
      <Card className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <CardTitle>Live Monitoring</CardTitle>
          <CardDescription>
            Keyboard: `1/4/9/0` changes camera grid on this page.
          </CardDescription>
        </div>
        <div className="flex items-center gap-2">
          {gridOptions.map((size) => (
            <Button
              key={size}
              size="sm"
              variant={liveGridSize === size ? "default" : "ghost"}
              onClick={() => setLiveGridSize(size)}
              className="font-mono"
            >
              {size}
            </Button>
          ))}
        </div>
      </Card>

      <div className="grid gap-3 xl:grid-cols-[minmax(0,1fr)_340px]">
        <div className="space-y-3">
          <CameraGrid
            cameras={scopedCameras}
            tiles={liveTiles.data}
            gridSize={liveGridSize}
          />
        </div>
        <AlertRail alerts={alerts.data ?? []} />
      </div>
    </div>
  );
}
