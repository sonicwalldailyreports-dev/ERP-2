from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Notification


class NotificationRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_for_user(self, user_id: UUID, *, unread_only: bool = False, limit: int = 50) -> list[Notification]:
        query = select(Notification).where(Notification.user_id == user_id)
        if unread_only:
            query = query.where(Notification.read_at.is_(None))
        return list(
            await self.session.scalars(
                query.order_by(Notification.created_at.desc()).limit(max(1, min(limit, 200)))
            )
        )

    async def unread_count(self, user_id: UUID) -> int:
        return int(
            await self.session.scalar(
                select(func.count()).select_from(Notification).where(
                    Notification.user_id == user_id, Notification.read_at.is_(None)
                )
            )
            or 0
        )

    async def get_for_user(self, notification_id: UUID, user_id: UUID) -> Notification | None:
        return await self.session.scalar(
            select(Notification).where(Notification.id == notification_id, Notification.user_id == user_id)
        )

    async def mark_read(self, notification: Notification) -> Notification:
        notification.read_at = notification.read_at or datetime.now(UTC)
        await self.session.commit()
        await self.session.refresh(notification)
        return notification

    async def mark_all_read(self, user_id: UUID) -> int:
        result = await self.session.execute(
            update(Notification)
            .where(Notification.user_id == user_id, Notification.read_at.is_(None))
            .values(read_at=datetime.now(UTC))
        )
        await self.session.commit()
        return int(result.rowcount or 0)
