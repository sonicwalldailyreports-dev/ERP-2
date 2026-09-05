"""Notification abstraction with durable in-app and optional email delivery."""

from __future__ import annotations

import asyncio
import smtplib
from collections.abc import Iterable
from typing import ClassVar, Protocol
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import redact_sensitive
from app.core.config import Settings
from app.db.models import BackgroundJob, Notification
from app.modules.notifications.events import (
    APPROVAL_PENDING,
    EXPENSE_APPROVED,
    EXPENSE_REJECTED,
    EXPENSE_SUBMITTED,
    PASSWORD_RESET,
    PAYMENT_RECEIVED,
    USER_CREATED,
    DomainEvent,
)
from app.modules.notifications.repository import NotificationRepository


class EmailSender(Protocol):
    async def send(self, recipient: str, subject: str, body: str) -> None: ...


class NullEmailSender:
    async def send(self, recipient: str, subject: str, body: str) -> None:
        return None


class SMTPEmailSender:
    """Optional SMTP adapter; importing this module never opens a connection."""

    def __init__(self, host: str, port: int, sender: str, username: str | None = None,
                 password: str | None = None, use_tls: bool = True):
        self.host, self.port, self.sender = host, port, sender
        self.username, self.password, self.use_tls = username, password, use_tls

    async def send(self, recipient: str, subject: str, body: str) -> None:
        await asyncio.to_thread(self._send, recipient, subject, body)

    def _send(self, recipient: str, subject: str, body: str) -> None:
        from email.message import EmailMessage

        message = EmailMessage()
        message["From"], message["To"], message["Subject"] = self.sender, recipient, subject
        message.set_content(body)
        with smtplib.SMTP(self.host, self.port, timeout=15) as smtp:
            if self.use_tls:
                smtp.starttls()
            if self.username:
                smtp.login(self.username, self.password or "")
            smtp.send_message(message)


def create_email_sender(settings: Settings) -> EmailSender:
    if settings.email_enabled and settings.smtp_host:
        return SMTPEmailSender(
            settings.smtp_host,
            settings.smtp_port,
            settings.email_from,
            settings.smtp_username,
            settings.smtp_password,
            settings.smtp_use_tls,
        )
    return NullEmailSender()


class NotificationService:
    """Application-facing notification API.

    In-app records are written with the caller's transaction. Email is represented
    by a durable job and therefore can never make financial posting asynchronous.
    """

    _COPY: ClassVar[dict[str, tuple[str, str]]] = {
        EXPENSE_SUBMITTED: ("Expense submitted", "An expense is awaiting review."),
        EXPENSE_APPROVED: ("Expense approved", "An expense has been approved."),
        EXPENSE_REJECTED: ("Expense rejected", "An expense has been rejected."),
        PAYMENT_RECEIVED: ("Payment received", "A payment was received."),
        APPROVAL_PENDING: ("Approval pending", "An item is awaiting your approval."),
        USER_CREATED: ("User created", "Your user account has been created."),
        PASSWORD_RESET: ("Password reset", "Password reset instructions are available."),
    }

    def __init__(self, session: AsyncSession, settings: Settings | None = None):
        self.session = session
        self.settings = settings
        self.repository = NotificationRepository(session)

    async def notify(
        self,
        event: DomainEvent,
        recipients: Iterable[UUID],
        *,
        title: str | None = None,
        message: str | None = None,
        email: bool = False,
    ) -> list[Notification]:
        default_title, default_message = self._COPY.get(
            event.event_type, (event.event_type, "A new notification is available.")
        )
        safe_payload = redact_sensitive(event.payload)
        email_requested = email and (self.settings is None or self.settings.email_enabled)
        created: list[Notification] = []
        for recipient in set(recipients):
            key = f"{event.key()}:{recipient}"
            existing = await self.session.scalar(
                select(Notification).where(Notification.idempotency_key == key)
            )
            if existing is not None:
                created.append(existing)
                continue
            notification = Notification(
                user_id=recipient,
                company_id=event.company_id,
                branch_id=event.branch_id,
                event_type=event.event_type,
                title=title or default_title,
                message=message or default_message,
                payload=safe_payload,
                idempotency_key=key,
            )
            self.session.add(notification)
            created.append(notification)
            if email_requested:
                self.session.add(
                    BackgroundJob(
                        kind="email",
                        company_id=event.company_id,
                        branch_id=event.branch_id,
                        payload={
                            "event_type": event.event_type,
                            "recipient_user_id": str(recipient),
                            "subject": title or default_title,
                            "body": message or default_message,
                            **(
                                {
                                    "password_reset_token_id": str(
                                        event.payload["password_reset_token_id"]
                                    )
                                }
                                if "password_reset_token_id" in event.payload
                                else {}
                            ),
                        },
                        idempotency_key=f"email:{key}",
                        max_attempts=self.settings.task_queue_max_retries
                        if self.settings
                        else 3,
                    )
                )
        return created

    async def publish(self, event: DomainEvent, *, recipients: Iterable[UUID] | None = None, email: bool = False):
        target_ids = list(recipients or ([event.user_id] if event.user_id else []))
        if not target_ids:
            return []
        return await self.notify(event, target_ids, email=email)

    async def send_in_app(self, event: DomainEvent, recipients: Iterable[UUID]) -> list[Notification]:
        return await self.notify(event, recipients)

    async def send_email(self, event: DomainEvent, recipients: Iterable[UUID]) -> list[Notification]:
        return await self.notify(event, recipients, email=True)

    async def publish_event(
        self, event: DomainEvent, *, recipients: Iterable[UUID] | None = None, email: bool = False
    ) -> list[Notification]:
        return await self.publish(event, recipients=recipients, email=email)

    async def list(self, user_id: UUID, *, unread_only: bool = False, limit: int = 50) -> tuple[list[Notification], int]:
        return await self.repository.list_for_user(
            user_id, unread_only=unread_only, limit=limit
        ), await self.repository.unread_count(user_id)

    async def mark_read(self, notification_id: UUID, user_id: UUID) -> Notification:
        notification = await self.repository.get_for_user(notification_id, user_id)
        if notification is None:
            raise ValueError("Notification not found.")
        return await self.repository.mark_read(notification)

    async def mark_all_read(self, user_id: UUID) -> int:
        return await self.repository.mark_all_read(user_id)
