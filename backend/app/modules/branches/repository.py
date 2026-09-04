from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Branch, UserBranch


class BranchRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_for_user(self, company_id: UUID, user_id: UUID) -> list[Branch]:
        result = await self.session.scalars(
            select(Branch)
            .join(
                UserBranch,
                (UserBranch.branch_id == Branch.id)
                & (UserBranch.company_id == Branch.company_id),
            )
            .where(
                Branch.company_id == company_id,
                UserBranch.user_id == user_id,
                Branch.deleted_at.is_(None),
            )
            .order_by(Branch.name)
        )
        return list(result)

    async def get_for_user(self, branch_id: UUID, company_id: UUID, user_id: UUID) -> Branch | None:
        return await self.session.scalar(
            select(Branch)
            .join(
                UserBranch,
                (UserBranch.branch_id == Branch.id)
                & (UserBranch.company_id == Branch.company_id),
            )
            .where(
                Branch.id == branch_id,
                Branch.company_id == company_id,
                UserBranch.user_id == user_id,
                Branch.deleted_at.is_(None),
            )
        )
