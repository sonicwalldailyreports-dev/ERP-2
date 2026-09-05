"""Durable background-job foundation.

The application only persists jobs in the request transaction. A separate
worker calls :class:`BackgroundWorker`; the default queue is deliberately
in-process for local development and tests. Redis can be supplied by an
adapter without making Redis a runtime dependency of the web process.
"""

import asyncio
import inspect
import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.db.models import BackgroundJob, PasswordResetToken, User
from app.modules.auth.security import password_reset_token

logger = logging.getLogger(__name__)

EMAIL_JOB = "email"
REPORT_JOB = "report.generate"
SCHEDULED_REPORT_JOB = "report.scheduled"
CLEANUP_JOB = "cleanup"


class TaskQueue(Protocol):
    async def enqueue(self, job_id: UUID) -> None: ...


class InProcessTaskQueue:
    """Small, deterministic queue suitable for a single-process deployment."""

    def __init__(self):
        self.items: asyncio.Queue[UUID] = asyncio.Queue()

    async def enqueue(self, job_id: UUID) -> None:
        await self.items.put(job_id)

    async def get(self) -> UUID:
        return await self.items.get()

    def __len__(self) -> int:
        return self.items.qsize()


class RedisTaskQueue:
    """Adapter for an already-created redis client (redis-py or fakeredis)."""

    def __init__(self, client: Any, key: str = "small-office:jobs"):
        self.client = client
        self.key = key

    async def enqueue(self, job_id: UUID) -> None:
        result = self.client.rpush(self.key, str(job_id))
        if inspect.isawaitable(result):
            await result


class ResilientTaskQueue:
    """Use an external queue when available and never block local persistence."""

    def __init__(self, primary: TaskQueue, fallback: InProcessTaskQueue | None = None):
        self.primary = primary
        self.fallback = fallback or InProcessTaskQueue()

    async def enqueue(self, job_id: UUID) -> None:
        try:
            await self.primary.enqueue(job_id)
        except Exception:
            logger.warning("External task queue unavailable; using in-process queue.", exc_info=True)
            await self.fallback.enqueue(job_id)


def create_task_queue(settings: Settings, redis_client: Any | None = None) -> TaskQueue:
    """Select Redis only when explicitly configured; safely fall back locally."""
    if settings.task_queue_backend == "redis" and redis_client is not None:
        return ResilientTaskQueue(RedisTaskQueue(redis_client))
    return InProcessTaskQueue()


async def enqueue_job(
    session: AsyncSession,
    kind: str,
    payload: dict[str, Any],
    *,
    idempotency_key: str,
    max_attempts: int = 3,
    queue: TaskQueue | None = None,
    company_id: UUID | None = None,
    branch_id: UUID | None = None,
) -> BackgroundJob:
    """Create a job once and optionally hand it to an external queue."""
    job = await session.scalar(
        select(BackgroundJob).where(BackgroundJob.idempotency_key == idempotency_key)
    )
    if job is None:
        if branch_id is not None and company_id is None:
            raise ValueError("A branch-scoped job requires a company scope.")
        job = BackgroundJob(
            kind=kind,
            company_id=company_id,
            branch_id=branch_id,
            payload=payload,
            idempotency_key=idempotency_key,
            max_attempts=max(1, max_attempts),
        )
        session.add(job)
        await session.flush()
    if queue is not None:
        await queue.enqueue(job.id)
    return job


class JobService:
    """Convenience API used by request handlers and schedulers."""

    def __init__(
        self, session: AsyncSession, settings: Settings | None = None, queue: TaskQueue | None = None
    ):
        self.session = session
        self.settings = settings or Settings()
        self.queue = queue

    async def enqueue(
        self,
        kind: str,
        payload: dict[str, Any],
        *,
        idempotency_key: str,
        max_attempts: int | None = None,
        company_id: UUID | None = None,
        branch_id: UUID | None = None,
    ) -> BackgroundJob:
        return await enqueue_job(
            self.session,
            kind,
            payload,
            idempotency_key=idempotency_key,
            max_attempts=max_attempts or self.settings.task_queue_max_retries,
            queue=self.queue,
            company_id=company_id,
            branch_id=branch_id,
        )

    async def email(
        self, payload: dict[str, Any], *, idempotency_key: str, company_id: UUID | None = None,
        branch_id: UUID | None = None,
    ) -> BackgroundJob:
        return await self.enqueue(
            EMAIL_JOB, payload, idempotency_key=idempotency_key,
            company_id=company_id, branch_id=branch_id,
        )

    async def generate_report(self, payload: dict[str, Any], *, idempotency_key: str) -> BackgroundJob:
        return await self.enqueue(REPORT_JOB, payload, idempotency_key=idempotency_key)

    async def scheduled_report(self, payload: dict[str, Any], *, idempotency_key: str) -> BackgroundJob:
        return await self.enqueue(SCHEDULED_REPORT_JOB, payload, idempotency_key=idempotency_key)

    async def cleanup(self, payload: dict[str, Any], *, idempotency_key: str) -> BackgroundJob:
        return await self.enqueue(CLEANUP_JOB, payload, idempotency_key=idempotency_key)


JobHandler = Callable[[AsyncSession, dict[str, Any]], Awaitable[None]]


class BackgroundWorker:
    """Executes persisted jobs with exponential retry and terminal failures."""

    def __init__(
        self,
        settings: Settings | None = None,
        handlers: dict[str, JobHandler] | None = None,
        email_sender: Any | None = None,
    ):
        self.settings = settings or Settings()
        self.email_sender = email_sender
        self.handlers = handlers or {}

    async def run_once(
        self,
        session: AsyncSession,
        job_id: UUID | None = None,
        *,
        company_id: UUID | None = None,
        branch_id: UUID | None = None,
    ) -> BackgroundJob | None:
        query = select(BackgroundJob).where(
            BackgroundJob.status == "pending",
            BackgroundJob.available_at <= datetime.now(UTC),
        )
        if job_id is not None:
            query = query.where(BackgroundJob.id == job_id)
        if company_id is not None:
            query = query.where(BackgroundJob.company_id == company_id)
        if branch_id is not None:
            query = query.where(BackgroundJob.branch_id == branch_id)
        # Keep the claim inside the transaction.  PostgreSQL workers skip rows
        # claimed by another worker instead of executing the same job twice.
        job = await session.scalar(
            query.order_by(BackgroundJob.created_at).with_for_update(skip_locked=True).limit(1)
        )
        if job is None:
            return None
        job.status = "running"
        job.started_at = datetime.now(UTC)
        job.attempts += 1
        await session.commit()
        try:
            handler = self.handlers.get(job.kind)
            if handler is None:
                raise RuntimeError(f"No handler registered for job kind '{job.kind}'.")
            await handler(session, job.payload)
        except Exception as exc:  # noqa: BLE001 - worker must persist retry state
            job.last_error = str(exc)[:2000]
            if job.attempts < job.max_attempts:
                job.status = "pending"
                delay = self.settings.task_queue_retry_delay_seconds * (2 ** (job.attempts - 1))
                job.available_at = datetime.now(UTC) + timedelta(seconds=delay)
            else:
                job.status = "failed"
            await session.commit()
            logger.warning("Background job %s failed (attempt %s): %s", job.id, job.attempts, exc)
            return job
        job.status = "completed"
        job.completed_at = datetime.now(UTC)
        job.last_error = None
        await session.commit()
        return job

    async def run_until_empty(
        self,
        session: AsyncSession,
        limit: int = 100,
        *,
        company_id: UUID | None = None,
        branch_id: UUID | None = None,
    ) -> int:
        completed = 0
        for _ in range(max(0, limit)):
            job = await self.run_once(session, company_id=company_id, branch_id=branch_id)
            if job is None:
                break
            if job.status == "completed":
                completed += 1
        return completed

    async def run_queued(
        self,
        session: AsyncSession,
        queue: InProcessTaskQueue,
        limit: int = 100,
        *,
        company_id: UUID | None = None,
        branch_id: UUID | None = None,
    ) -> int:
        completed = 0
        for _ in range(max(0, limit)):
            if len(queue) == 0:
                break
            job = await self.run_once(
                session, await queue.get(), company_id=company_id, branch_id=branch_id
            )
            if job is not None and job.status == "completed":
                completed += 1
        return completed


async def email_job_handler(
    session: AsyncSession, payload: dict[str, Any], sender: Any, settings: Settings | None = None
) -> None:
    user = await session.get(User, UUID(payload["recipient_user_id"]))
    if user is None or not user.email:
        return
    body = payload["body"]
    token_id = payload.get("password_reset_token_id")
    if token_id and settings is not None:
        reset = await session.get(PasswordResetToken, UUID(token_id))
        if reset is not None and reset.used_at is None:
            body = f"{body}\nToken: {password_reset_token(token_id, settings)}"
    await sender.send(user.email, payload["subject"], body)


def default_handlers(
    email_sender: Any | None = None, settings: Settings | None = None
) -> dict[str, JobHandler]:
    worker_settings = settings or Settings()

    async def email(session: AsyncSession, payload: dict[str, Any]) -> None:
        if email_sender is None:
            return
        await email_job_handler(session, payload, email_sender, worker_settings)

    async def report(_session: AsyncSession, _payload: dict[str, Any]) -> None:
        # Report generation is intentionally an integration point. The report
        # service remains synchronous for interactive requests.
        return None

    async def cleanup(_session: AsyncSession, _payload: dict[str, Any]) -> None:
        return None

    return {
        EMAIL_JOB: email,
        REPORT_JOB: report,
        SCHEDULED_REPORT_JOB: report,
        CLEANUP_JOB: cleanup,
    }
