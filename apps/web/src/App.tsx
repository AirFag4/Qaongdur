import { AuthScreen } from "./auth/auth-screen";
import { useAuth } from "./auth/use-auth";
import { Navigate, Route, Routes } from "react-router-dom";
import { LoadingState } from "@qaongdur/ui";
import { OperatorLayout } from "./app/operator-layout";
import { AlertsEventsPage } from "./pages/alerts-events-page";
import { CropGalleryPage } from "./pages/crop-gallery-page";
import { DevicesPage } from "./pages/devices-page";
import { IncidentDetailPage } from "./pages/incident-detail-page";
import { LiveMonitoringPage } from "./pages/live-monitoring-page";
import { OverviewPage } from "./pages/overview-page";
import { PlaybackSearchPage } from "./pages/playback-search-page";

function App() {
  const auth = useAuth();

  if (auth.status === "loading") {
    return <LoadingState label="Connecting to Keycloak..." />;
  }

  if (auth.status === "error") {
    return <AuthScreen error={auth.error} />;
  }

  if (auth.status === "unauthenticated") {
    return <AuthScreen onLogin={() => auth.login()} />;
  }

  return (
    <Routes>
      <Route element={<OperatorLayout />}>
        <Route index element={<OverviewPage />} />
        <Route path="live" element={<LiveMonitoringPage />} />
        <Route path="alerts" element={<AlertsEventsPage />} />
        <Route path="incidents" element={<IncidentDetailPage />} />
        <Route path="incidents/:incidentId" element={<IncidentDetailPage />} />
        <Route path="playback" element={<PlaybackSearchPage />} />
        <Route path="crops" element={<CropGalleryPage />} />
        <Route path="devices" element={<DevicesPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default App;
