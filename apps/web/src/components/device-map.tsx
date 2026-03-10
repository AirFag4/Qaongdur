import { useEffect, useRef } from "react";
import maplibregl, { LngLatBounds } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import type { DeviceMapCamera, HealthStatus } from "@qaongdur/types";
import { EmptyState } from "@qaongdur/ui";

const mapStyle: maplibregl.StyleSpecification = {
  version: 8,
  sources: {
    osm: {
      type: "raster",
      tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
      tileSize: 256,
      attribution: "\u00a9 OpenStreetMap contributors",
    },
  },
  layers: [
    {
      id: "osm",
      type: "raster",
      source: "osm",
    },
  ],
};

const markerColorByHealth: Record<HealthStatus, string> = {
  healthy: "#10b981",
  warning: "#f59e0b",
  critical: "#ef4444",
  offline: "#64748b",
};

export function DeviceMap({
  cameras,
  selectedCameraId,
  onSelectCamera,
  themeMode,
}: {
  cameras: DeviceMapCamera[];
  selectedCameraId?: string;
  onSelectCamera: (cameraId: string) => void;
  themeMode: "polarized-dark" | "polarized-light";
}) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);

  useEffect(() => {
    if (!containerRef.current || !cameras.length) {
      return;
    }

    const map = new maplibregl.Map({
      container: containerRef.current,
      style: mapStyle,
      center: [cameras[0].longitude, cameras[0].latitude],
      zoom: cameras.length === 1 ? 14 : 12,
      cooperativeGestures: true,
    });
    mapRef.current = map;
    map.addControl(new maplibregl.NavigationControl({ showCompass: true }), "top-right");

    const markers = cameras.map((camera) => {
      const marker = document.createElement("button");
      marker.type = "button";
      marker.title = camera.name;
      marker.style.width = "18px";
      marker.style.height = "18px";
      marker.style.borderRadius = "9999px";
      marker.style.border = camera.cameraId === selectedCameraId
        ? `3px solid ${themeMode === "polarized-dark" ? "#f8fafc" : "#0f172a"}`
        : `2px solid ${themeMode === "polarized-dark" ? "#111827" : "#ffffff"}`;
      marker.style.background = markerColorByHealth[camera.health];
      marker.style.boxShadow = "0 0 0 1px rgba(15, 23, 42, 0.18)";
      marker.style.cursor = "pointer";
      marker.addEventListener("click", () => onSelectCamera(camera.cameraId));

      return new maplibregl.Marker({
        element: marker,
        rotation: camera.heading ?? 0,
        rotationAlignment: "map",
      })
        .setLngLat([camera.longitude, camera.latitude])
        .addTo(map);
    });

    const fitMap = () => {
      if (!cameras.length) {
        return;
      }
      if (cameras.length === 1) {
        map.easeTo({
          center: [cameras[0].longitude, cameras[0].latitude],
          zoom: 14,
          duration: 600,
        });
        return;
      }
      const bounds = new LngLatBounds();
      cameras.forEach((camera) => bounds.extend([camera.longitude, camera.latitude]));
      map.fitBounds(bounds, {
        padding: 48,
        duration: 600,
        maxZoom: 15,
      });
    };

    map.on("load", fitMap);
    map.on("error", () => undefined);

    return () => {
      markers.forEach((marker) => marker.remove());
      map.remove();
      mapRef.current = null;
    };
  }, [cameras, onSelectCamera, selectedCameraId, themeMode]);

  if (!cameras.length) {
    return (
      <EmptyState
        title="No mapped cameras"
        description="Add latitude and longitude during camera onboarding to place cameras on the device map."
      />
    );
  }

  return <div ref={containerRef} className="h-[420px] w-full overflow-hidden rounded-xl border border-[var(--qa-card-border)]" />;
}
