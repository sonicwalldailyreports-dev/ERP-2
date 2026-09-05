from __future__ import annotations

import json
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AuditLog, Company
from app.modules.companies.repository import CompanyRepository
from app.modules.companies.schemas import CompanyCreate, CompanyUpdate


class CompanyService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repository = CompanyRepository(session)

    async def list(self, user_id: UUID) -> list[Company]:
        return await self.repository.list_for_user(user_id)

    async def get(self, company_id: UUID, user_id: UUID) -> Company:
        company = await self.repository.get_for_user(company_id, user_id)
        if company is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found.")
        return company

    async def create(self, data: CompanyCreate, user_id: UUID) -> Company:
        company = Company(**data.model_dump())
        await self.repository.add(company, user_id)
        await self._audit("CREATE", company, user_id)
        await self.session.commit()
        return company

    async def update(self, company_id: UUID, data: CompanyUpdate, user_id: UUID) -> Company:
        company = await self.get(company_id, user_id)
        for key, value in data.model_dump(exclude_unset=True).items():
            setattr(company, key, value)
        await self._audit("UPDATE", company, user_id)
        await self.session.commit()
        return company

    async def set_active(self, company_id: UUID, active: bool, user_id: UUID) -> Company:
        company = await self.get(company_id, user_id)
        company.is_active = active
        await self._audit("ACTIVATE" if active else "DEACTIVATE", company, user_id)
        await self.session.commit()
        return company

    async def _audit(self, action: str, company: Company, user_id: UUID) -> None:
        self.session.add(
            AuditLog(
                company_id=company.id,
                user_id=user_id,
                action=action,
                entity_type="company",
                entity_id=company.id,
                details=json.dumps({"name": company.name, "code": company.code}),
            )
        )
