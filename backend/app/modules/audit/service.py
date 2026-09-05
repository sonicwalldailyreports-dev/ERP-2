from __future__ import annotations

from math import ceil
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import has_permission
from app.db.models import UserBranch, UserCompany
from app.modules.audit.repository import AuditRepository
from app.modules.audit.schemas import AuditLogFilters


class AuditService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repository = AuditRepository(session)

    async def list(self, actor_id: UUID, filters: AuditLogFilters, dev: bool) -> dict:
        company_ids: set[UUID] | None = None
        if not dev:
            # A system role is the only role that is intentionally global.
            global_access = await has_permission(self.session, actor_id, "audit.audit.view")
            if not global_access:
                company_ids = set(
                    await self.session.scalars(
                        select(UserCompany.company_id).where(UserCompany.user_id == actor_id)
                    )
                )
                if filters.company_id is not None and filters.company_id not in company_ids:
                    raise HTTPException(status_code=403, detail="Organization scope is not allowed.")
                if filters.branch_id is not None:
                    branch_scope = await self.session.scalar(
                        select(UserBranch.branch_id).where(
                            UserBranch.user_id == actor_id,
                            UserBranch.branch_id == filters.branch_id,
                            UserBranch.company_id == filters.company_id,
                        )
                    )
                    if branch_scope is None:
                        raise HTTPException(status_code=403, detail="Organization scope is not allowed.")
            elif filters.company_id is not None:
                # The dependency already validates assigned scope for non-global users.
                company_ids = None

        rows, total = await self.repository.list(
            date_from=filters.date_from,
            date_to=filters.date_to,
            user_id=filters.user_id,
            module=filters.module,
            action=filters.action,
            entity=filters.entity,
            entity_id=filters.entity_id,
            company_id=filters.company_id,
            branch_id=filters.branch_id,
            company_ids=company_ids,
            page=filters.page,
            page_size=filters.page_size,
        )
        return {
            "items": rows,
            "total": total,
            "page": filters.page,
            "page_size": filters.page_size,
            "pages": ceil(total / filters.page_size) if total else 0,
        }
