from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import Account, Branch, Company, FinancialYear, Transaction


class FinancialTransactionRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, transaction_id: UUID, *, lock: bool = False) -> Transaction | None:
        query = (
            select(Transaction)
            .options(selectinload(Transaction.lines))
            .where(Transaction.id == transaction_id)
        )
        if lock:
            query = query.with_for_update()
        return await self.session.scalar(query)

    async def list(
        self,
        company_id: UUID,
        branch_id: UUID | None = None,
        status: str | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[Transaction]:
        query = select(Transaction).options(selectinload(Transaction.lines)).where(
            Transaction.company_id == company_id
        )
        if branch_id is not None:
            query = query.where(Transaction.branch_id == branch_id)
        if status is not None:
            query = query.where(Transaction.status == status)
        if start_date is not None:
            query = query.where(Transaction.transaction_date >= start_date)
        if end_date is not None:
            query = query.where(Transaction.transaction_date <= end_date)
        return list(
            await self.session.scalars(
                query.order_by(Transaction.transaction_date.desc(), Transaction.created_at.desc())
            )
        )

    async def company(self, company_id: UUID) -> Company | None:
        return await self.session.scalar(
            select(Company).where(Company.id == company_id, Company.is_active.is_(True))
        )

    async def branch(self, company_id: UUID, branch_id: UUID) -> Branch | None:
        return await self.session.scalar(
            select(Branch).where(Branch.id == branch_id, Branch.company_id == company_id)
        )

    async def financial_year(self, company_id: UUID, year_id: UUID) -> FinancialYear | None:
        return await self.session.scalar(
            select(FinancialYear).where(
                FinancialYear.id == year_id, FinancialYear.company_id == company_id
            )
        )

    async def account(self, company_id: UUID, account_id: UUID, *, lock: bool = False) -> Account | None:
        query = select(Account).where(
            Account.id == account_id,
            Account.company_id == company_id,
            Account.deleted_at.is_(None),
        )
        if lock:
            query = query.with_for_update()
        return await self.session.scalar(query)

    async def existing_number(self, company_id: UUID, number: str) -> Transaction | None:
        return await self.session.scalar(
            select(Transaction).where(
                Transaction.company_id == company_id,
                Transaction.transaction_number == number,
            )
        )

    async def reversal(self, transaction_id: UUID) -> Transaction | None:
        return await self.session.scalar(
            select(Transaction).where(Transaction.reversal_of_id == transaction_id)
        )


TransactionRepository = FinancialTransactionRepository
