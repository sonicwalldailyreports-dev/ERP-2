from uuid import UUID

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.jobs import BackgroundWorker, InProcessTaskQueue, enqueue_job
from app.db.models import BackgroundJob, Notification
from app.modules.notifications.events import USER_CREATED, DomainEvent
from app.modules.notifications.service import NotificationService
from tests.conftest import TEST_USER_ID


@pytest.mark.asyncio
async def test_notification_event_is_idempotent(test_app):
    async with test_app.state.session_factory() as session:
        event = DomainEvent(USER_CREATED, subject_id=TEST_USER_ID, user_id=TEST_USER_ID)
        service = NotificationService(session)
        await service.publish(event)
        await session.commit()
        await service.publish(event)
        await session.commit()
        rows = list(await session.scalars(select(Notification)))
        assert len(rows) == 1


@pytest.mark.asyncio
async def test_background_job_idempotency_and_retry(test_app):
    async with test_app.state.session_factory() as session:
        queue = InProcessTaskQueue()
        first = await enqueue_job(
            session, "test", {"value": 1}, idempotency_key="test-key", max_attempts=3, queue=queue
        )
        await session.commit()
        second = await enqueue_job(
            session, "test", {"value": 2}, idempotency_key="test-key", max_attempts=3, queue=queue
        )
        assert first.id == second.id
        await session.commit()
        attempts = 0

        async def flaky(_session: AsyncSession, _payload: dict):
            nonlocal attempts
            attempts += 1
            if attempts < 3:
                raise RuntimeError("try again")

        worker = BackgroundWorker(Settings(task_queue_retry_delay_seconds=0), {"test": flaky})
        assert (await worker.run_once(session, first.id)).status == "pending"
        assert (await worker.run_once(session, first.id)).status == "pending"
        assert (await worker.run_once(session, first.id)).status == "completed"
        stored = await session.get(BackgroundJob, first.id)
        assert stored is not None and stored.attempts == 3


@pytest.mark.asyncio
async def test_in_process_queue_preserves_job_identity():
    queue = InProcessTaskQueue()
    job_id = UUID("00000000-0000-0000-0000-000000000099")
    await queue.enqueue(job_id)
    assert await queue.get() == job_id
