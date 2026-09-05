from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Branch, Company, Customer


class CustomerRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, customer_id: UUID) -> Customer | None:
        return await self.session.scalar(
            select(Customer).where(Customer.id == customer_id, Customer.deleted_at.is_(None))
        )

    async def find_code(self, company_id: UUID, code: str, exclude_id: UUID | None = None) -> Customer | None:
        query = select(Customer).where(Customer.company_id == company_id, Customer.customer_code == code)
        if exclude_id is not None:
            query = query.where(Customer.id != exclude_id)
        return await self.session.scalar(query)

    async def valid_company(self, company_id: UUID) -> Company | None:
        return await self.session.scalar(
            select(Company).where(Company.id == company_id, Company.is_active.is_(True))
        )

    async def valid_branch(self, company_id: UUID, branch_id: UUID) -> Branch | None:
        return await self.session.scalar(
            select(Branch).where(
                Branch.id == branch_id,
                Branch.company_id == company_id,
                Branch.is_active.is_(True),
            )
        )

    async def list(
        self,
        company_id: UUID | None,
        branch_id: UUID | None,
        search: str | None,
        status: str | None,
        page: int,
        page_size: int,
    ) -> tuple[list[Customer], int]:
        query = select(Customer).where(Customer.deleted_at.is_(None))
        if company_id is not None:
            query = query.where(Customer.company_id == company_id)
        if branch_id is not None:
            query = query.where(or_(Customer.branch_id == branch_id, Customer.branch_id.is_(None)))
        if search:
            term = f"%{search.strip().lower()}%"
            query = query.where(
                or_(
                    func.lower(Customer.customer_code).like(term),
                    func.lower(Customer.name).like(term),
                    func.lower(Customer.contact_person).like(term),
                    func.lower(Customer.email).like(term),
                    func.lower(Customer.phone).like(term),
                    func.lower(Customer.tax_id).like(term),
                )
            )
        if status:
            query = query.where(Customer.status == status)
        total = int(await self.session.scalar(select(func.count()).select_from(query.subquery())) or 0)
        rows = list(
            await self.session.scalars(
                query.order_by(Customer.name, Customer.customer_code)
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        return rows, total
