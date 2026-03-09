import { useEffect, useMemo, useState } from "react";
import { Outlet, useLocation, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import type { CameraGridSize, CommandPaletteItem } from "@qaongdur/ui";
import {
  AppShell,
  type AppNavItem,
  CommandPalette,
  LoadingState,
  SiteCameraSwitcher,
} from "@qaongdur/ui";
import type { RealtimeEvent } from "@qaongdur/types";
import { apiClient, queryKeys, realtimeSocket } from "../lib/api";
import { AgentChatRail } from "../components/agent-chat-rail";
import type { OperatorOutletContext } from "./operator-context";

const navItems: AppNavItem[] = [
  { id: "overview", label: "Overview", path: "/", shortcut: "Alt+1" },
  { id: "live", label: "Live", path: "/live", shortcut: "Alt+2" },
  { id: "alerts", label: "Alerts", path: "/alerts", shortcut: "Alt+3" },
  { id: "incidents", label: "Incident", path: "/incidents", shortcut: "Alt+4" },
  { id: "playback", label: "Playback", path: "/playback", shortcut: "Alt+5" },
  { id: "devices", label: "Devices", path: "/devices", shortcut: "Alt+6" },
  { id: "crops", label: "Crops", path: "/crops", shortcut: "Alt+7" },
  { id: "settings", label: "Settings", path: "/settings", shortcut: "Alt+8" },
];

const isEditableTarget = (target: EventTarget | null) => {
  if (!(target instanceof HTMLElement)) {
    return false;
  }
  return (
    target.tagName === "INPUT" ||
    target.tagName === "TEXTAREA" ||
    target.tagName === "SELECT" ||
    target.isContentEditable
  );
};

const pathToNavPath = (path: string) => {
  if (path.startsWith("/incidents")) {
    return "/incidents";
  }
  return path;
};

export function OperatorLayout() {
  const navigate = useNavigate();
  const location = useLocation();
  const [siteId, setSiteId] = useState<string | undefined>();
  const [selectedCameraIds, setSelectedCameraIds] = useState<string[]>([]);
  const [liveGridSize, setLiveGridSize] = useState<CameraGridSize>(4);
  const [commandPaletteOpen, setCommandPaletteOpen] = useState(false);
  const [recentEvents, setRecentEvents] = useState<RealtimeEvent[]>([]);
  const [themeMode, setThemeMode] = useState<"polarized-dark" | "polarized-light">(() =>
    window.localStorage.getItem("qaongdur-theme-mode") === "polarized-light"
      ? "polarized-light"
      : "polarized-dark",
  );

  const sites = useQuery({
    queryKey: queryKeys.sites,
    queryFn: () => apiClient.listSites(),
  });
  const cameras = useQuery({
    queryKey: queryKeys.cameras(siteId),
    queryFn: () => apiClient.listCameras(siteId),
  });

  useEffect(() => {
    window.localStorage.setItem("qaongdur-theme-mode", themeMode);
  }, [themeMode]);

  useEffect(() => {
    const unsubscribe = realtimeSocket.subscribe((event) => {
      setRecentEvents((previous) => [event, ...previous].slice(0, 12));
    });
    realtimeSocket.connect();
    return () => {
      unsubscribe();
      realtimeSocket.disconnect();
    };
  }, []);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (isEditableTarget(event.target)) {
        return;
      }

      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setCommandPaletteOpen(true);
        return;
      }

      if (event.altKey) {
        const navTarget = navItems[Number(event.key) - 1];
        if (navTarget) {
          event.preventDefault();
          navigate(navTarget.path);
          return;
        }
      }

      if (location.pathname.startsWith("/live")) {
        if (event.key === "1") {
          setLiveGridSize(1);
        }
        if (event.key === "4") {
          setLiveGridSize(4);
        }
        if (event.key === "9") {
          setLiveGridSize(9);
        }
        if (event.key === "0") {
          setLiveGridSize(16);
        }
      }
    };

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [location.pathname, navigate]);

  const toggleCameraSelection = (cameraId: string) => {
    setSelectedCameraIds((previous) =>
      previous.includes(cameraId)
        ? previous.filter((id) => id !== cameraId)
        : [...previous, cameraId],
    );
  };

  const commandItems = useMemo<CommandPaletteItem[]>(
    () => [
      ...navItems.map((item) => ({
        id: `nav-${item.id}`,
        label: `Go to ${item.label}`,
        group: "Navigation",
        shortcut: item.shortcut,
        run: () => navigate(item.path),
      })),
      {
        id: "grid-1",
        label: "Live grid: 1 camera",
        group: "Live Grid",
        run: () => setLiveGridSize(1),
      },
      {
        id: "grid-4",
        label: "Live grid: 4 cameras",
        group: "Live Grid",
        run: () => setLiveGridSize(4),
      },
      {
        id: "grid-9",
        label: "Live grid: 9 cameras",
        group: "Live Grid",
        run: () => setLiveGridSize(9),
      },
      {
        id: "grid-16",
        label: "Live grid: 16 cameras",
        group: "Live Grid",
        run: () => setLiveGridSize(16),
      },
    ],
    [navigate],
  );

  if (sites.isLoading || cameras.isLoading || !sites.data || !cameras.data) {
    return <LoadingState label="Booting operator workspace..." />;
  }

  const outletContext: OperatorOutletContext = {
    sites: sites.data,
    cameras: cameras.data,
    siteId,
    selectedCameraIds,
    liveGridSize,
    recentEvents,
    setSiteId: (nextSiteId) => {
      setSiteId(nextSiteId);
      setSelectedCameraIds([]);
    },
    toggleCameraSelection,
    setLiveGridSize,
    openCommandPalette: () => setCommandPaletteOpen(true),
  };

  return (
    <>
      <AppShell
        navItems={navItems}
        activePath={pathToNavPath(location.pathname)}
        onNavigate={navigate}
        onOpenCommandPalette={() => setCommandPaletteOpen(true)}
        siteSwitcher={
          <SiteCameraSwitcher
            sites={sites.data}
            cameras={cameras.data}
            siteId={siteId}
            selectedCameraIds={selectedCameraIds}
            onSiteChange={(nextSiteId) => {
              setSiteId(nextSiteId);
              setSelectedCameraIds([]);
            }}
            onCameraToggle={toggleCameraSelection}
          />
        }
        rightRail={<AgentChatRail recentEvents={recentEvents} realtimeMode={realtimeSocket.mode} />}
        themeMode={themeMode}
        onToggleThemeMode={() =>
          setThemeMode((currentMode) =>
            currentMode === "polarized-dark" ? "polarized-light" : "polarized-dark",
          )
        }
      >
        <Outlet context={outletContext} />
      </AppShell>
      <CommandPalette
        open={commandPaletteOpen}
        onClose={() => setCommandPaletteOpen(false)}
        items={commandItems}
      />
    </>
  );
}
