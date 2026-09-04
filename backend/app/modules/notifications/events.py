"""Business events understood by the notification and job layers."""

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

EXPENSE_SUBMITTED = "expense.submitted"
EXPENSE_APPROVED = "expense.approved"
EXPENSE_REJECTED = "expense.rejected"
PAYMENT_RECEIVED = "payment.received"
APPROVAL_PENDING = "approval.pending"
USER_CREATED = "user.created"
PASSWORD_RESET = "password.reset"

SUPPORTED_EVENTS = frozenset(
    {
        EXPENSE_SUBMITTED,
        EXPENSE_APPROVED,
        EXPENSE_REJECTED,
        PAYMENT_RECEIVED,
        APPROVAL_PENDING,
        USER_CREATED,
        PASSWORD_RESET,
    }
)


@dataclass(frozen=True, slots=True)
class DomainEvent:
    event_type: str
    subject_id: UUID | None = None
    user_id: UUID | None = None
    company_id: UUID | None = None
    branch_id: UUID | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    idempotency_key: str | None = None

    def key(self) -> str:
        return self.idempotency_key or f"{self.event_type}:{self.subject_id or 'event'}"
