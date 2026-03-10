import { useQuery } from "@tanstack/react-query";
import { Badge, Button, Card, CardDescription, CardTitle, EmptyState, LoadingState } from "@qaongdur/ui";
import { useAuth } from "../auth/use-auth";
import { getKeycloakAdminUsersUrl, getKeycloakClient } from "../auth/keycloak";
import { apiClient, queryKeys } from "../lib/api";
import {
  createRecentInputRangeInTimeZone,
  formatDateTimeInTimeZone,
  getOperatorTimeZoneLabel,
  getOperatorTimeZoneOptions,
} from "../lib/bkk-time";
import { useOperatorOutlet } from "../app/use-operator-outlet";

const formatBytes = (bytes: number) => {
  if (bytes >= 1024 * 1024 * 1024) {
    return `${(bytes / (1024 * 1024 * 1024)).toFixed(1)} GB`;
  }
  if (bytes >= 1024 * 1024) {
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  }
  return `${bytes} B`;
};

export function SettingsPage() {
  const auth = useAuth();
  const { operatorTimeZone, setOperatorTimeZone } = useOperatorOutlet();
  const isRealmAdmin = Boolean(
    getKeycloakClient().tokenParsed?.realm_access?.roles?.includes("realm-admin"),
  );

  const keycloakAdminUsersUrl = getKeycloakAdminUsersUrl();
  const settings = useQuery({
    queryKey: queryKeys.systemSettings,
    queryFn: () => apiClient.getSystemSettings(),
  });
  const timeZoneOptions = getOperatorTimeZoneOptions();
  const previewRange = createRecentInputRangeInTimeZone(operatorTimeZone);

  if (settings.isLoading) {
    return <LoadingState label="Loading runtime settings..." />;
  }

  if (settings.isError || !settings.data) {
    return (
      <EmptyState
        title="Settings unavailable"
        description="The control API settings endpoint could not be loaded."
      />
    );
  }

  return (
    <div className="space-y-3">
      <div className="grid gap-3 xl:grid-cols-[minmax(0,1.1fr)_minmax(320px,420px)]">
        <Card className="space-y-3">
          <div className="flex items-center justify-between gap-3">
            <div>
              <CardTitle>Authentication</CardTitle>
              <CardDescription>
                Session and access controls moved here so operations pages stay focused on cameras and incidents.
              </CardDescription>
            </div>
            <Badge tone="cyan">Live</Badge>
          </div>

          <div className="rounded-md border border-stone-700 bg-stone-950/60 p-3 text-sm text-stone-300">
            <p className="font-medium text-stone-100">{auth.session?.user.displayName}</p>
            <p>{auth.session?.user.email ?? auth.session?.user.username}</p>
            <p className="mt-2 text-xs text-stone-500">
              Issuer: <span className="font-mono">{settings.data.auth.issuer}</span>
            </p>
            <p className="text-xs text-stone-500">
              Audience: <span className="font-mono">{settings.data.auth.audience}</span>
            </p>
            <div className="mt-3 flex flex-wrap gap-2">
              {(auth.session?.user.roles ?? []).map((role) => (
                <Badge key={role} tone="stone">
                  {role}
                </Badge>
              ))}
            </div>
          </div>

          <div className="flex flex-wrap gap-2">
            <Button size="sm" variant="secondary" onClick={() => void auth.registerPasskey()}>
              Register Passkey
            </Button>
            {isRealmAdmin && keycloakAdminUsersUrl ? (
              <Button
                size="sm"
                variant="secondary"
                onClick={() => window.open(keycloakAdminUsersUrl, "_blank", "noopener,noreferrer")}
              >
                Add User In Keycloak
              </Button>
            ) : null}
            <Button size="sm" variant="ghost" onClick={() => void auth.requestStepUp("settings-auth-review")}>
              Step-Up Reauth
            </Button>
            <Button size="sm" variant="secondary" onClick={() => void auth.logout()}>
              Sign Out
            </Button>
          </div>
        </Card>

        <Card className="space-y-3">
          <div>
            <CardTitle>Operator Preferences</CardTitle>
            <CardDescription>
              Personal UI preferences stored in this browser for search windows and timestamp display.
            </CardDescription>
          </div>
          <div className="space-y-3 rounded-md border border-stone-700 bg-stone-950/60 p-3 text-sm text-stone-300">
            <div className="space-y-1">
              <label className="text-xs uppercase tracking-wide text-stone-500">
                Timezone
              </label>
              <select
                className="form-input"
                value={operatorTimeZone}
                onChange={(event) => setOperatorTimeZone(event.target.value as typeof operatorTimeZone)}
              >
                {timeZoneOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </div>
            <div className="grid gap-2 md:grid-cols-2">
              <div className="rounded-md border border-stone-700 bg-stone-900/60 p-3">
                <p className="text-xs uppercase tracking-wide text-stone-500">
                  Active zone
                </p>
                <p className="mt-1">{getOperatorTimeZoneLabel(operatorTimeZone)}</p>
              </div>
              <div className="rounded-md border border-stone-700 bg-stone-900/60 p-3">
                <p className="text-xs uppercase tracking-wide text-stone-500">
                  Default search window
                </p>
                <p className="mt-1">
                  {formatDateTimeInTimeZone(previewRange.from, operatorTimeZone)} to{" "}
                  {formatDateTimeInTimeZone(previewRange.to, operatorTimeZone)}
                </p>
                <p className="mt-1 text-xs text-stone-500">10 minutes</p>
              </div>
            </div>
          </div>
        </Card>

        <Card className="space-y-3">
          <div>
            <CardTitle>Runtime Summary</CardTitle>
            <CardDescription>
              Current env-backed defaults for recording, playback, and automatic vision ingest.
            </CardDescription>
          </div>
          <div className="space-y-2 rounded-md border border-stone-700 bg-stone-950/60 p-3 text-sm text-stone-300">
            <div className="flex items-center justify-between gap-2">
              <span>Recording chunk</span>
              <span>{settings.data.recording.segmentDurationSeconds}s</span>
            </div>
            <div className="flex items-center justify-between gap-2">
              <span>Playback base</span>
              <span className="font-mono text-xs">{settings.data.recording.playbackPublicUrl}</span>
            </div>
            <div className="flex items-center justify-between gap-2">
              <span>Live HLS base</span>
              <span className="font-mono text-xs">{settings.data.recording.hlsPublicUrl}</span>
            </div>
            <div className="flex items-center justify-between gap-2">
              <span>Vision service</span>
              <span className="font-mono text-xs">{settings.data.vision.serviceUrl}</span>
            </div>
            <div className="flex items-center justify-between gap-2">
              <span>Auto ingest</span>
              <span>{settings.data.vision.autoIngest ? "enabled" : "disabled"}</span>
            </div>
            <div className="flex items-center justify-between gap-2">
              <span>Object embeddings</span>
              <span>{settings.data.vision.embeddingEnabled ? "enabled" : "disabled"}</span>
            </div>
            <div className="flex items-center justify-between gap-2">
              <span>Face embeddings</span>
              <span>{settings.data.vision.faceEnabled ? "enabled" : "disabled"}</span>
            </div>
          </div>
        </Card>

        <Card className="space-y-3">
          <div>
            <CardTitle>Media Storage Budget</CardTitle>
            <CardDescription>
              Shared storage budget for playback recordings and crop investigation artifacts.
            </CardDescription>
          </div>
          <div className="space-y-2 rounded-md border border-stone-700 bg-stone-950/60 p-3 text-sm text-stone-300">
            <div className="flex items-center justify-between gap-2">
              <span>Total media budget</span>
              <span>{formatBytes(settings.data.mediaStorage.totalLimitBytes)}</span>
            </div>
            <div className="flex items-center justify-between gap-2">
              <span>Playback allocation</span>
              <span>
                {formatBytes(settings.data.mediaStorage.recordingLimitBytes)} •{" "}
                {settings.data.mediaStorage.recordingSharePercent}%
              </span>
            </div>
            <div className="flex items-center justify-between gap-2">
              <span>Crop allocation</span>
              <span>
                {formatBytes(settings.data.mediaStorage.artifactLimitBytes)} •{" "}
                {settings.data.mediaStorage.artifactSharePercent}%
              </span>
            </div>
            <div className="h-2 overflow-hidden rounded bg-stone-800">
              <div
                className="h-full bg-cyan-400"
                style={{ width: `${settings.data.mediaStorage.recordingSharePercent}%` }}
              />
            </div>
            <div className="flex items-center justify-between gap-2 text-xs text-stone-500">
              <span>Playback / recordings</span>
              <span>Crop artifacts</span>
            </div>
          </div>
        </Card>
      </div>

      <Card className="space-y-3">
        <div>
          <CardTitle>Planning Notes</CardTitle>
          <CardDescription>
            This page is the configuration planning surface for the next writable settings pass.
          </CardDescription>
        </div>
        <div className="grid gap-2 md:grid-cols-2">
          {settings.data.vision.notes.map((note) => (
            <div key={note} className="rounded-md border border-stone-700 bg-stone-950/60 p-3 text-sm text-stone-300">
              {note}
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
