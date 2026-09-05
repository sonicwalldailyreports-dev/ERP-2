from __future__ import annotations

from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Branch, Company, FinancialYear, NumberSequence


def make_scope_key(
    company_id: UUID,
    document_type: str,
    branch_id: UUID | None,
    financial_year_id: UUID | None,
) -> str:
    branch = str(branch_id) if branch_id is not None else "*"
    year = str(financial_year_id) if financial_year_id is not None else "*"
    return f"{company_id}:{branch}:{year}:{document_type.strip().lower()}"


class NumberSequenceRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, sequence_id: UUID, for_update: bool = False) -> NumberSequence | None:
        query = select(NumberSequence).where(NumberSequence.id == sequence_id)
        if for_update:
            query = query.with_for_update()
        return await self.session.scalar(query)

    async def get_by_scope(
        self,
        company_id: UUID,
        document_type: str,
        branch_id: UUID | None,
        financial_year_id: UUID | None,
    ) -> NumberSequence | None:
        return await self.session.scalar(
            select(NumberSequence).where(
                NumberSequence.scope_key
                == make_scope_key(company_id, document_type, branch_id, financial_year_id)
            )
        )

    async def list(self, company_id: UUID, branch_id: UUID | None = None) -> list[NumberSequence]:
        query = select(NumberSequence).where(NumberSequence.company_id == company_id)
        if branch_id is not None:
            query = query.where(NumberSequence.branch_id == branch_id)
        return list(await self.session.scalars(query.order_by(NumberSequence.document_type)))

    async def valid_company(self, company_id: UUID) -> bool:
        return bool(await self.session.scalar(select(Company.id).where(Company.id == company_id)))

    async def valid_branch(self, company_id: UUID, branch_id: UUID) -> bool:
        return bool(
            await self.session.scalar(
                select(Branch.id).where(Branch.id == branch_id, Branch.company_id == company_id)
            )
        )

    async def financial_year(
        self, company_id: UUID, financial_year_id: UUID
    ) -> FinancialYear | None:
        return await self.session.scalar(
            select(FinancialYear).where(
                FinancialYear.id == financial_year_id,
                FinancialYear.company_id == company_id,
            )
        )

    async def increment(self, sequence_id: UUID) -> tuple[int, NumberSequence] | None:
        sequence = await self.get(sequence_id)
        if sequence is None or not sequence.is_active:
            return None
        result = await self.session.execute(
            update(NumberSequence)
            .where(NumberSequence.id == sequence_id, NumberSequence.is_active.is_(True))
            .values(next_number=NumberSequence.next_number + 1)
            .returning(NumberSequence.next_number)
        )
        row = result.first()
        if row is None:
            return None
        sequence.next_number = int(row[0])
        return sequence.next_number - 1, sequence
