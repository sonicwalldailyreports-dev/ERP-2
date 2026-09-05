from __future__ import annotations

import json
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AuditLog, Branch, UserBranch
from app.modules.branches.repository import BranchRepository
from app.modules.branches.schemas import BranchCreate, BranchUpdate
from app.modules.companies.repository import CompanyRepository


class BranchService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repository = BranchRepository(session)
        self.companies = CompanyRepository(session)

    async def list(self, company_id: UUID, user_id: UUID) -> list[Branch]:
        await self._company(company_id, user_id)
        return await self.repository.list_for_user(company_id, user_id)

    async def get(self, company_id: UUID, branch_id: UUID, user_id: UUID) -> Branch:
        await self._company(company_id, user_id)
        branch = await self.repository.get_for_user(branch_id, company_id, user_id)
        if branch is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Branch not found.")
        return branch

    async def create(self, data: BranchCreate, user_id: UUID) -> Branch:
        await self._company(data.company_id, user_id)
        branch = Branch(**data.model_dump())
        self.session.add(branch)
        await self.session.flush()
        self.session.add(UserBranch(user_id=user_id, company_id=branch.company_id, branch_id=branch.id))
        await self._audit("CREATE", branch, user_id)
        await self.session.commit()
        return branch

    async def update(self, company_id: UUID, branch_id: UUID, data: BranchUpdate, user_id: UUID) -> Branch:
        branch = await self.get(company_id, branch_id, user_id)
        for key, value in data.model_dump(exclude_unset=True).items():
            setattr(branch, key, value)
        await self._audit("UPDATE", branch, user_id)
        await self.session.commit()
        return branch

    async def set_active(self, company_id: UUID, branch_id: UUID, active: bool, user_id: UUID) -> Branch:
        branch = await self.get(company_id, branch_id, user_id)
        branch.is_active = active
        await self._audit("ACTIVATE" if active else "DEACTIVATE", branch, user_id)
        await self.session.commit()
        return branch

    async def _company(self, company_id: UUID, user_id: UUID):
        company = await self.companies.get_for_user(company_id, user_id)
        if company is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found.")
        return company

    async def _audit(self, action: str, branch: Branch, user_id: UUID) -> None:
        self.session.add(
            AuditLog(
                company_id=branch.company_id,
                branch_id=branch.id,
                user_id=user_id,
                action=action,
                entity_type="branch",
                entity_id=branch.id,
                details=json.dumps({"name": branch.name, "code": branch.code}),
            )
        )
