import { useQuery } from "@tanstack/react-query";
import { Badge, Button, Card, CardDescription, CardTitle, EmptyState, LoadingState } from "@qaongdur/ui";
import { useAuth } from "../auth/use-auth";
import { apiClient, queryKeys } from "../lib/api";

export function SettingsPage() {
  const auth = useAuth();
  const settings = useQuery({
    queryKey: queryKeys.systemSettings,
    queryFn: () => apiClient.getSystemSettings(),
  });

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
