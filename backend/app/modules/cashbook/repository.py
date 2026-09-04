from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    Branch,
    CashAccount,
    CashOpeningBalance,
    CashTransaction,
    Company,
    FinancialYear,
)


class CashBookRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def company(self, company_id: UUID) -> Company | None:
        return await self.session.scalar(select(Company).where(Company.id == company_id, Company.is_active.is_(True)))

    async def branch(self, company_id: UUID, branch_id: UUID) -> Branch | None:
        return await self.session.scalar(select(Branch).where(Branch.id == branch_id, Branch.company_id == company_id))

    async def financial_year(self, company_id: UUID, year_id: UUID) -> FinancialYear | None:
        return await self.session.scalar(select(FinancialYear).where(FinancialYear.id == year_id, FinancialYear.company_id == company_id))

    async def financial_year_for_date(self, company_id: UUID, value: date) -> FinancialYear | None:
        return await self.session.scalar(select(FinancialYear).where(
            FinancialYear.company_id == company_id, FinancialYear.start_date <= value,
            FinancialYear.end_date >= value,
        ))

    async def account(self, account_id: UUID, *, lock: bool = False) -> CashAccount | None:
        query = select(CashAccount).where(CashAccount.id == account_id, CashAccount.deleted_at.is_(None))
        if lock:
            query = query.with_for_update()
        return await self.session.scalar(query)

    async def list_accounts(self, company_id: UUID, branch_id: UUID | None) -> list[CashAccount]:
        query = select(CashAccount).where(
            CashAccount.company_id == company_id, CashAccount.deleted_at.is_(None),
            CashAccount.branch_id.is_(None) if branch_id is None else (CashAccount.branch_id == branch_id) | CashAccount.branch_id.is_(None),
        )
        return list(await self.session.scalars(query.order_by(CashAccount.account_code)))

    async def list_transactions(
        self, company_id: UUID, branch_id: UUID | None, state: str | None, account_id: UUID | None,
        start_date: date | None, end_date: date | None,
    ) -> list[CashTransaction]:
        query = select(CashTransaction).where(CashTransaction.company_id == company_id)
        if branch_id is not None:
            query = query.where(CashTransaction.branch_id == branch_id)
        if state:
            query = query.where(CashTransaction.state == state)
        if account_id:
            query = query.where(or_(CashTransaction.cash_account_id == account_id, CashTransaction.target_cash_account_id == account_id))
        if start_date:
            query = query.where(CashTransaction.transaction_date >= start_date)
        if end_date:
            query = query.where(CashTransaction.transaction_date <= end_date)
        return list(await self.session.scalars(query.order_by(CashTransaction.transaction_date.desc(), CashTransaction.created_at.desc())))

    async def transaction(self, transaction_id: UUID, *, lock: bool = False) -> CashTransaction | None:
        query = select(CashTransaction).where(CashTransaction.id == transaction_id)
        if lock:
            query = query.with_for_update()
        return await self.session.scalar(query)

    async def opening(self, account_id: UUID, year_id: UUID) -> CashOpeningBalance | None:
        return await self.session.scalar(select(CashOpeningBalance).where(
            CashOpeningBalance.cash_account_id == account_id, CashOpeningBalance.financial_year_id == year_id
        ))

    async def list_openings(self, company_id: UUID, branch_id: UUID | None = None) -> list[CashOpeningBalance]:
        query = select(CashOpeningBalance).join(CashAccount, CashAccount.id == CashOpeningBalance.cash_account_id).where(
            CashOpeningBalance.company_id == company_id,
            CashAccount.branch_id.is_(None) if branch_id is None else (
                CashAccount.branch_id == branch_id
            ) | CashAccount.branch_id.is_(None),
        )
        return list(await self.session.scalars(query.order_by(CashOpeningBalance.created_at.desc())))

    async def posted_for_day(self, company_id: UUID, branch_id: UUID | None, account_id: UUID, summary_date: date) -> list[CashTransaction]:
        query = select(CashTransaction).where(
            CashTransaction.company_id == company_id, CashTransaction.transaction_date == summary_date,
            CashTransaction.state == "POSTED",
            or_(CashTransaction.cash_account_id == account_id, CashTransaction.target_cash_account_id == account_id),
        )
        if branch_id is not None:
            query = query.where(CashTransaction.branch_id == branch_id)
        return list(await self.session.scalars(query))

    async def posted_balance(self, account_id: UUID, until: date | None = None) -> Decimal:
        query = select(CashTransaction).where(
            CashTransaction.state == "POSTED",
            or_(CashTransaction.cash_account_id == account_id, CashTransaction.target_cash_account_id == account_id),
        )
        if until is not None:
            query = query.where(CashTransaction.transaction_date <= until)
        rows = list(await self.session.scalars(query))
        total = Decimal(0)
        for row in rows:
            if row.transaction_type == "receipt" or row.target_cash_account_id == account_id:
                total += row.amount
            else:
                total -= row.amount
        return total
