from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from datetime import UTC, datetime

from .auth import KeycloakPrincipal


@dataclass(slots=True)
class AuditLogEntry:
    acting_user_id: str
    acting_username: str
    acting_roles: list[str]
    action: str
    timestamp: str
    approval_path: list[str]
    step_up_acr: str | None
    outcome: str
    note: str | None = None


class AuditLogger:
    def __init__(self) -> None:
        self._logger = logging.getLogger("qaongdur.audit")

    def record(
        self,
        *,
        principal: KeycloakPrincipal,
        action: str,
        approval_path: list[str],
        outcome: str,
        note: str | None = None,
    ) -> AuditLogEntry:
        entry = AuditLogEntry(
            acting_user_id=principal.subject,
            acting_username=principal.username,
            acting_roles=sorted(principal.roles),
            action=action,
            timestamp=datetime.now(tz=UTC).isoformat(),
            approval_path=approval_path,
            step_up_acr=principal.acr,
            outcome=outcome,
            note=note,
        )
        self._logger.info("audit_entry=%s", asdict(entry))
        return entry


audit_logger = AuditLogger()
