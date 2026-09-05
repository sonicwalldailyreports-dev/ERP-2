from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Branch, Company, Vendor


class VendorRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, vendor_id: UUID) -> Vendor | None:
        return await self.session.scalar(
            select(Vendor).where(Vendor.id == vendor_id, Vendor.deleted_at.is_(None))
        )

    async def find_code(self, company_id: UUID, code: str, exclude_id: UUID | None = None) -> Vendor | None:
        query = select(Vendor).where(Vendor.company_id == company_id, Vendor.vendor_code == code)
        if exclude_id is not None:
            query = query.where(Vendor.id != exclude_id)
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
    ) -> tuple[list[Vendor], int]:
        query = select(Vendor).where(Vendor.deleted_at.is_(None))
        if company_id is not None:
            query = query.where(Vendor.company_id == company_id)
        if branch_id is not None:
            query = query.where(or_(Vendor.branch_id == branch_id, Vendor.branch_id.is_(None)))
        if search and search.strip():
            term = f"%{search.strip().lower()}%"
            query = query.where(
                or_(
                    func.lower(Vendor.vendor_code).like(term),
                    func.lower(Vendor.name).like(term),
                    func.lower(Vendor.company_name).like(term),
                    func.lower(Vendor.contact_person).like(term),
                    func.lower(Vendor.email).like(term),
                    func.lower(Vendor.phone).like(term),
                    func.lower(Vendor.tax_id).like(term),
                    func.lower(Vendor.tax_number).like(term),
                )
            )
        if status:
            query = query.where(Vendor.status == status)
        total = int(await self.session.scalar(select(func.count()).select_from(query.subquery())) or 0)
        rows = list(
            await self.session.scalars(
                query.order_by(Vendor.name, Vendor.vendor_code)
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        return rows, total
