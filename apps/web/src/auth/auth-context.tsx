import type { PropsWithChildren } from "react";
import { startTransition, useEffect, useState } from "react";
import type {
  KeycloakLoginOptions,
  KeycloakProfile,
  KeycloakTokenParsed,
} from "keycloak-js";
import type { AuthSession, PlatformRole } from "@qaongdur/types";
import {
  getAuthConfigError,
  getKeycloakClient,
  getStepUpAcr,
  initKeycloak,
} from "./keycloak";
import { AuthContext, type AuthStatus } from "./auth-context-store";

const platformRoles: PlatformRole[] = [
  "platform-admin",
  "site-admin",
  "operator",
  "reviewer",
  "viewer",
];

const initialError = getAuthConfigError();

const extractRoles = (token: KeycloakTokenParsed | undefined) => {
  const roleSet = new Set<PlatformRole>();
  const realmRoles = token?.realm_access?.roles ?? [];

  realmRoles.forEach((role) => {
    if (platformRoles.includes(role as PlatformRole)) {
      roleSet.add(role as PlatformRole);
    }
  });

  Object.values(token?.resource_access ?? {}).forEach((resource) => {
    resource.roles.forEach((role) => {
      if (platformRoles.includes(role as PlatformRole)) {
        roleSet.add(role as PlatformRole);
      }
    });
  });

  return Array.from(roleSet).sort();
};

const buildSession = (
  token: KeycloakTokenParsed | undefined,
  profile: KeycloakProfile | undefined,
  accessToken: string,
  idToken?: string,
): AuthSession => {
  const username = token?.preferred_username ?? profile?.username ?? token?.sub ?? "unknown";
  const displayName =
    token?.name ??
    [profile?.firstName, profile?.lastName].filter(Boolean).join(" ") ??
    username;

  return {
    accessToken,
    idToken,
    expiresAt: token?.exp ? token.exp * 1000 : undefined,
    user: {
      id: token?.sub ?? username,
      username,
      displayName: displayName || username,
      email: token?.email ?? profile?.email,
      roles: extractRoles(token),
      acr: token?.acr,
    },
  };
};

export function AuthProvider({ children }: PropsWithChildren) {
  const [status, setStatus] = useState<AuthStatus>(initialError ? "error" : "loading");
  const [session, setSession] = useState<AuthSession>();
  const [error, setError] = useState<string | undefined>(initialError);

  useEffect(() => {
    if (initialError) {
      return;
    }

    const client = getKeycloakClient();
    let isMounted = true;

    const syncSession = async () => {
      if (!client.authenticated || !client.token) {
        if (isMounted) {
          startTransition(() => {
            setSession(undefined);
            setStatus("unauthenticated");
          });
        }
        return;
      }

      const profile = await client.loadUserProfile().catch(() => undefined);
      const nextSession = buildSession(
        client.tokenParsed,
        profile,
        client.token,
        client.idToken,
      );

      if (isMounted) {
        startTransition(() => {
          setSession(nextSession);
          setStatus("authenticated");
          setError(undefined);
        });
      }
    };

    client.onAuthSuccess = () => {
      void syncSession();
    };
    client.onAuthRefreshSuccess = () => {
      void syncSession();
    };
    client.onAuthLogout = () => {
      if (isMounted) {
        startTransition(() => {
          setSession(undefined);
          setStatus("unauthenticated");
        });
      }
    };
    client.onTokenExpired = () => {
      void client
        .updateToken(30)
        .then((refreshed) => {
          if (refreshed) {
            return syncSession();
          }
          return undefined;
        })
        .catch(async () => {
          await client.login({ redirectUri: window.location.href });
        });
    };

    void initKeycloak()
      .then((authenticated) => {
        if (!isMounted) {
          return;
        }

        if (!authenticated) {
          setStatus("unauthenticated");
          return;
        }

        return syncSession();
      })
      .catch((caughtError: unknown) => {
        if (!isMounted) {
          return;
        }

        const message =
          caughtError instanceof Error
            ? caughtError.message
            : "Unable to initialize the Keycloak browser session.";

        setError(message);
        setStatus("error");
      });

    return () => {
      isMounted = false;
      client.onAuthSuccess = undefined;
      client.onAuthRefreshSuccess = undefined;
      client.onAuthLogout = undefined;
      client.onTokenExpired = undefined;
    };
  }, []);

  useEffect(() => {
    if (status !== "authenticated") {
      return;
    }

    const client = getKeycloakClient();
    const refreshTimer = window.setInterval(() => {
      void client.updateToken(60).catch(() => undefined);
    }, 20_000);

    return () => window.clearInterval(refreshTimer);
  }, [status]);

  const login = async (options?: KeycloakLoginOptions) => {
    await getKeycloakClient().login({
      redirectUri: window.location.href,
      ...options,
    });
  };

  const logout = async () => {
    await getKeycloakClient().logout({
      redirectUri: window.location.origin,
    });
  };

  const registerPasskey = async () => {
    await login({ action: "webauthn-register-passwordless" });
  };

  const requestStepUp = async (reason: string) => {
    void reason;
    await login({
      prompt: "login",
      maxAge: 0,
      acrValues: getStepUpAcr(),
      redirectUri: window.location.href,
      loginHint: session?.user.email ?? session?.user.username,
    });
  };

  const hasAnyRole = (roles: PlatformRole[]) =>
    Boolean(session && roles.some((role) => session.user.roles.includes(role)));

  return (
    <AuthContext.Provider
      value={{
        status,
        session,
        error,
        login,
        logout,
        registerPasskey,
        requestStepUp,
        hasAnyRole,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}
