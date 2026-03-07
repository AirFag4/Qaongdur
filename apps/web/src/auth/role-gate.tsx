import type { PropsWithChildren, ReactNode } from "react";
import type { PlatformRole } from "@qaongdur/types";
import { useAuth } from "./use-auth";

interface RoleGateProps extends PropsWithChildren {
  anyOf: PlatformRole[];
  fallback?: ReactNode;
}

export function RoleGate({ anyOf, fallback = null, children }: RoleGateProps) {
  const auth = useAuth();

  if (!auth.hasAnyRole(anyOf)) {
    return <>{fallback}</>;
  }

  return <>{children}</>;
}
