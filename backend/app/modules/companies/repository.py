from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Company, UserCompany


class CompanyRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_for_user(self, user_id: UUID) -> list[Company]:
        result = await self.session.scalars(
            select(Company)
            .join(UserCompany, UserCompany.company_id == Company.id)
            .where(UserCompany.user_id == user_id, Company.deleted_at.is_(None))
            .order_by(Company.name)
        )
        return list(result)

    async def get_for_user(self, company_id: UUID, user_id: UUID) -> Company | None:
        return await self.session.scalar(
            select(Company)
            .join(UserCompany, UserCompany.company_id == Company.id)
            .where(
                Company.id == company_id,
                UserCompany.user_id == user_id,
                Company.deleted_at.is_(None),
            )
        )

    async def add(self, company: Company, user_id: UUID) -> Company:
        self.session.add(company)
        await self.session.flush()
        self.session.add(UserCompany(user_id=user_id, company_id=company.id))
        return company
