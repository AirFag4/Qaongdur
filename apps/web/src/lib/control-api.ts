import type { ApprovalResult, BackendAuthStatus } from "@qaongdur/types";
import { getControlApiBaseUrl } from "../auth/keycloak";

const sendJson = async <TResponse>(
  path: string,
  accessToken: string,
  init?: RequestInit,
): Promise<TResponse> => {
  const response = await fetch(`${getControlApiBaseUrl()}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${accessToken}`,
      ...(init?.headers ?? {}),
    },
  });

  if (!response.ok) {
    const errorBody = await response.text();
    throw new Error(errorBody || `Control API request failed with ${response.status}.`);
  }

  return (await response.json()) as TResponse;
};

export const fetchControlApiAuthStatus = (accessToken: string) =>
  sendJson<BackendAuthStatus>("/api/v1/auth/me", accessToken);

export const requestEvidenceExport = (accessToken: string) =>
  sendJson<ApprovalResult>("/api/v1/agent/actions/evidence-export", accessToken, {
    method: "POST",
    body: JSON.stringify({
      action: "agent.export-evidence",
      approvalPath: ["agent-rail", "approval-drawer", "confirm-export"],
      rationale: "Demo export approved in the operator console.",
      requiresStepUp: false,
    }),
  });

export const requestDestructivePurge = (accessToken: string) =>
  sendJson<ApprovalResult>("/api/v1/agent/actions/purge-evidence", accessToken, {
    method: "POST",
    body: JSON.stringify({
      action: "agent.purge-evidence",
      approvalPath: ["agent-rail", "danger-zone", "type-to-confirm"],
      rationale: "Demo destructive action requiring step-up authentication.",
      requiresStepUp: true,
    }),
  });
