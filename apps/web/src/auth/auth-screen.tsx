import { Badge, Button, Card, CardDescription, CardTitle } from "@qaongdur/ui";

interface AuthScreenProps {
  error?: string;
  onLogin?: () => Promise<void>;
}

export function AuthScreen({ error, onLogin }: AuthScreenProps) {
  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_18%_15%,rgba(34,211,238,0.15),transparent_28%),radial-gradient(circle_at_84%_20%,rgba(245,158,11,0.12),transparent_24%),linear-gradient(180deg,#11100f_0%,#090807_100%)] px-4 py-10 text-stone-100">
      <div className="mx-auto flex min-h-[calc(100vh-5rem)] max-w-6xl items-center">
        <div className="grid w-full gap-6 lg:grid-cols-[1.2fr_0.8fr]">
          <div className="space-y-5">
            <Badge tone="cyan">Keycloak Session Boundary</Badge>
            <div className="space-y-4">
              <h1 className="max-w-2xl text-4xl font-semibold tracking-tight text-stone-50">
                Qaongdur keeps the operator console, passkeys, and future agent approvals
                inside the same browser session.
              </h1>
              <p className="max-w-xl text-sm leading-6 text-stone-300">
                Login stays in Keycloak. Passkeys stay in the browser login UI. The
                in-app agent only acts through the existing authenticated session and
                backend role checks.
              </p>
            </div>
            {!error ? (
              <div className="flex flex-wrap gap-3">
                <Button size="lg" onClick={() => void onLogin?.()}>
                  Continue To Keycloak
                </Button>
                <Badge tone="stone" className="px-3 py-2 text-[12px] normal-case tracking-normal">
                  Existing passkeys can be used directly in the Keycloak login flow.
                </Badge>
              </div>
            ) : null}
          </div>

          <Card className="space-y-4 border-stone-700/90 bg-stone-950/85">
            <div className="space-y-2">
              <CardTitle>{error ? "Configuration Required" : "Auth Foundation"}</CardTitle>
              <CardDescription>
                {error
                  ? "The web app could not start the OIDC client."
                  : "Local dev defaults expect Keycloak on :8080 and the control API on :8000."}
              </CardDescription>
            </div>

            <div className="space-y-3 rounded-xl border border-stone-800 bg-stone-950/60 p-3 text-sm text-stone-300">
              <p>1. Start Keycloak from `infra/docker/compose.auth.yml`.</p>
              <p>2. Copy `apps/web/.env.example` to `apps/web/.env`.</p>
              <p>3. Sign in with one of the seeded realm users, then register a passkey from the app rail.</p>
            </div>

            <div className="rounded-xl border border-stone-800 bg-stone-950/60 p-3 text-xs leading-6 text-stone-400">
              {error ?? "Roles are enforced again by the control API using the same token."}
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
