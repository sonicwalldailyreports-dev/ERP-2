"""Shared audit context and payload handling.

The audit model is intentionally usable by existing services that still create
``AuditLog`` objects directly.  The model's insert hook calls the same
sanitizer and context binder, so legacy call sites cannot bypass redaction.
"""

from __future__ import annotations

import contextvars
import json
from collections.abc import Mapping
from dataclasses import dataclass, replace
from typing import Any
from uuid import UUID

_SENSITIVE_PARTS = (
    "password",
    "passwd",
    "token",
    "secret",
    "authorization",
    "credential",
    "api_key",
    "apikey",
    "cookie",
)
REDACTED = "[REDACTED]"


@dataclass(frozen=True)
class AuditRequestContext:
    request_id: str | None = None
    user_id: UUID | None = None
    ip_address: str | None = None
    user_agent: str | None = None


_context: contextvars.ContextVar[AuditRequestContext | None] = contextvars.ContextVar(
    "audit_request_context", default=None
)


def get_audit_context() -> AuditRequestContext:
    return _context.get() or AuditRequestContext()


def set_audit_context(**values: Any) -> contextvars.Token[AuditRequestContext]:
    """Bind request metadata for the current async task."""
    return _context.set(replace(get_audit_context(), **values))


def reset_audit_context(token: contextvars.Token[AuditRequestContext]) -> None:
    _context.reset(token)


def bind_audit_actor(user_id: UUID) -> None:
    """Add the authenticated actor without replacing request metadata."""
    _context.set(replace(get_audit_context(), user_id=user_id))


def _is_sensitive(key: str) -> bool:
    normalized = key.casefold().replace("-", "_")
    return any(part in normalized for part in _SENSITIVE_PARTS)


def redact_sensitive(value: Any) -> Any:
    """Return a JSON-compatible deep copy with secrets removed by key name."""
    if isinstance(value, Mapping):
        return {
            str(key): REDACTED if _is_sensitive(str(key)) else redact_sensitive(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple, set)):
        return [redact_sensitive(item) for item in value]
    if isinstance(value, UUID):
        return str(value)
    if hasattr(value, "isoformat") and callable(value.isoformat):
        return value.isoformat()
    return value


def redact_json_text(value: str | None) -> str | None:
    if value is None:
        return None
    try:
        return json.dumps(redact_sensitive(json.loads(value)), default=str)
    except (TypeError, ValueError):
        # Free-form legacy details are not allowed to carry likely credentials.
        lowered = value.casefold()
        if any(part in lowered for part in _SENSITIVE_PARTS):
            return REDACTED
        return value


async def record_audit(
    session: Any,
    *,
    action: str,
    module: str,
    entity: str,
    entity_id: UUID | None = None,
    user_id: UUID | None = None,
    company_id: UUID | None = None,
    branch_id: UUID | None = None,
    before: Any = None,
    after: Any = None,
    details: Any = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    request_id: str | None = None,
) -> Any:
    """Create an audit row without committing the caller's transaction."""
    from app.db.models import AuditLog

    context = get_audit_context()
    row = AuditLog(
        user_id=user_id if user_id is not None else context.user_id,
        company_id=company_id,
        branch_id=branch_id,
        action=action,
        module=module,
        entity_type=entity,
        entity_id=entity_id,
        before_data=redact_sensitive(before),
        after_data=redact_sensitive(after),
        details=(
            json.dumps(redact_sensitive(details), default=str)
            if details is not None and not isinstance(details, str)
            else redact_json_text(details)
        ),
        ip_address=ip_address if ip_address is not None else context.ip_address,
        user_agent=user_agent if user_agent is not None else context.user_agent,
        request_id=request_id if request_id is not None else context.request_id,
    )
    session.add(row)
    return row
