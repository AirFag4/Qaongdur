import { createContext } from "react";
import type { AuthSession, PlatformRole } from "@qaongdur/types";
import type { KeycloakLoginOptions } from "keycloak-js";

export type AuthStatus = "loading" | "authenticated" | "unauthenticated" | "error";

export interface AuthContextValue {
  status: AuthStatus;
  session?: AuthSession;
  error?: string;
  login: (options?: KeycloakLoginOptions) => Promise<void>;
  logout: () => Promise<void>;
  registerPasskey: () => Promise<void>;
  requestStepUp: (reason: string) => Promise<void>;
  hasAnyRole: (roles: PlatformRole[]) => boolean;
}

export const AuthContext = createContext<AuthContextValue | undefined>(undefined);
