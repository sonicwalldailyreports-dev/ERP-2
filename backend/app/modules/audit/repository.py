from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AuditLog


class AuditRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list(
        self,
        *,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        user_id: UUID | None = None,
        module: str | None = None,
        action: str | None = None,
        entity: str | None = None,
        entity_id: UUID | None = None,
        company_id: UUID | None = None,
        branch_id: UUID | None = None,
        company_ids: set[UUID] | None = None,
        page: int = 1,
        page_size: int = 25,
    ) -> tuple[list[AuditLog], int]:
        conditions = []
        if company_ids is not None:
            conditions.append(AuditLog.company_id.in_(company_ids))
        if company_id is not None:
            conditions.append(AuditLog.company_id == company_id)
        if branch_id is not None:
            conditions.append(AuditLog.branch_id == branch_id)
        if date_from is not None:
            conditions.append(AuditLog.created_at >= date_from)
        if date_to is not None:
            conditions.append(AuditLog.created_at <= date_to)
        if user_id is not None:
            conditions.append(AuditLog.user_id == user_id)
        if module is not None:
            conditions.append(AuditLog.module == module)
        if action is not None:
            conditions.append(AuditLog.action == action)
        if entity is not None:
            conditions.append(AuditLog.entity_type == entity)
        if entity_id is not None:
            conditions.append(AuditLog.entity_id == entity_id)
        count = await self.session.scalar(select(func.count(AuditLog.id)).where(*conditions)) or 0
        rows = list(
            await self.session.scalars(
                select(AuditLog)
                .where(*conditions)
                .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        return rows, count
