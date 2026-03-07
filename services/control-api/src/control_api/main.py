from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .audit import audit_logger
from .auth import (
    KeycloakPrincipal,
    PlatformRole,
    get_current_principal,
    has_required_acr,
    require_roles,
)
from .config import Settings, get_settings


class AgentApprovalBody(BaseModel):
    action: str
    approvalPath: list[str] = Field(default_factory=list)
    rationale: str | None = None
    requiresStepUp: bool = False


def _serialize_principal(principal: KeycloakPrincipal) -> dict[str, object]:
    return {
        "id": principal.subject,
        "username": principal.username,
        "displayName": principal.display_name,
        "email": principal.email,
        "roles": sorted(principal.roles),
        "acr": principal.acr,
    }


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="Qaongdur Control API",
        version="0.1.0",
        summary="Keycloak-protected control plane surface for Qaongdur",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.control_api_cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/v1/auth/me")
    async def get_auth_me(
        principal: Annotated[KeycloakPrincipal, Depends(get_current_principal)],
        service_settings: Annotated[Settings, Depends(get_settings)],
    ) -> dict[str, object]:
        return {
            "service": service_settings.service_name,
            "issuer": service_settings.keycloak_issuer_url,
            "audience": service_settings.keycloak_audience,
            "checkedAt": datetime.now(tz=UTC).isoformat(),
            "user": _serialize_principal(principal),
        }

    @app.get("/api/v1/auth/allowed-actions")
    async def get_allowed_actions(
        principal: Annotated[KeycloakPrincipal, Depends(get_current_principal)],
    ) -> dict[str, list[str]]:
        actions: list[str] = ["view-live", "view-alerts"]
        role_actions: dict[PlatformRole, list[str]] = {
            "viewer": [],
            "operator": ["acknowledge-alert", "launch-agent-investigation"],
            "reviewer": ["approve-evidence-export"],
            "site-admin": ["approve-site-maintenance", "override-camera-health"],
            "platform-admin": ["purge-evidence", "restart-edge-bridge"],
        }

        for role in sorted(principal.roles):
            actions.extend(role_actions.get(role, []))

        return {"actions": sorted(set(actions))}

    @app.post("/api/v1/agent/actions/evidence-export")
    async def export_evidence(
        body: AgentApprovalBody,
        principal: Annotated[
            KeycloakPrincipal,
            Depends(require_roles("operator", "reviewer", "site-admin", "platform-admin")),
        ],
    ) -> dict[str, object]:
        if not body.approvalPath:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="approvalPath must record the UI confirmation path.",
            )

        audit_entry = audit_logger.record(
            principal=principal,
            action=body.action,
            approval_path=body.approvalPath,
            outcome="approved",
            note=body.rationale,
        )

        return {
            "action": body.action,
            "approvalPath": body.approvalPath,
            "rationale": body.rationale,
            "requiresStepUp": body.requiresStepUp,
            "approved": True,
            "approvedAt": audit_entry.timestamp,
            "approvedBy": principal.username,
            "stepUpSatisfied": not body.requiresStepUp
            or has_required_acr(principal, get_settings().keycloak_step_up_acr),
        }

    @app.post("/api/v1/agent/actions/purge-evidence")
    async def purge_evidence(
        body: AgentApprovalBody,
        principal: Annotated[
            KeycloakPrincipal,
            Depends(require_roles("platform-admin")),
        ],
        service_settings: Annotated[Settings, Depends(get_settings)],
    ) -> dict[str, object]:
        if not body.approvalPath:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="approvalPath must record the UI confirmation path.",
            )

        if not has_required_acr(principal, service_settings.keycloak_step_up_acr):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "Step-up authentication required for destructive actions. "
                    f"Expected ACR {service_settings.keycloak_step_up_acr}."
                ),
            )

        audit_entry = audit_logger.record(
            principal=principal,
            action=body.action,
            approval_path=body.approvalPath,
            outcome="approved-with-step-up",
            note=body.rationale,
        )

        return {
            "action": body.action,
            "approvalPath": body.approvalPath,
            "rationale": body.rationale,
            "requiresStepUp": True,
            "approved": True,
            "approvedAt": audit_entry.timestamp,
            "approvedBy": principal.username,
            "stepUpSatisfied": True,
        }

    return app


app = create_app()


def run() -> None:
    settings = get_settings()
    uvicorn.run(
        "control_api.main:app",
        host=settings.control_api_host,
        port=settings.control_api_port,
        reload=settings.env == "development",
    )


if __name__ == "__main__":
    run()
