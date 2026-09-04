from datetime import date
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    Account,
    AccountType,
    Branch,
    CashAccount,
    Company,
    Expense,
    ExpenseCategory,
    FinancialYear,
)


class ExpenseRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

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

    async def category(self, category_id: UUID, company_id: UUID, branch_id: UUID | None) -> ExpenseCategory | None:
        return await self.session.scalar(
            select(ExpenseCategory).where(
                ExpenseCategory.id == category_id,
                ExpenseCategory.company_id == company_id,
                ExpenseCategory.is_active.is_(True),
                ExpenseCategory.branch_id.is_(None)
                if branch_id is None
                else or_(ExpenseCategory.branch_id == branch_id, ExpenseCategory.branch_id.is_(None)),
            )
        )

    async def category_by_code(self, company_id: UUID, code: str) -> ExpenseCategory | None:
        return await self.session.scalar(
            select(ExpenseCategory).where(
                ExpenseCategory.company_id == company_id, ExpenseCategory.code == code
            )
        )

    async def list_categories(self, company_id: UUID, branch_id: UUID | None) -> list[ExpenseCategory]:
        query = select(ExpenseCategory).where(ExpenseCategory.company_id == company_id)
        if branch_id is None:
            query = query.where(ExpenseCategory.branch_id.is_(None))
        else:
            query = query.where(
                or_(ExpenseCategory.branch_id == branch_id, ExpenseCategory.branch_id.is_(None))
            )
        return list(await self.session.scalars(query.order_by(ExpenseCategory.name)))

    async def account(self, account_id: UUID, company_id: UUID) -> Account | None:
        return await self.session.scalar(
            select(Account)
            .join(AccountType, AccountType.id == Account.account_type_id)
            .where(
                Account.id == account_id,
                Account.company_id == company_id,
                Account.deleted_at.is_(None),
                Account.is_active.is_(True),
                AccountType.code == "expense",
            )
        )

    async def cash_account(self, account_id: UUID, company_id: UUID) -> CashAccount | None:
        return await self.session.scalar(
            select(CashAccount).where(
                CashAccount.id == account_id,
                CashAccount.company_id == company_id,
                CashAccount.deleted_at.is_(None),
                CashAccount.is_active.is_(True),
            )
        )

    async def expense(self, expense_id: UUID, *, lock: bool = False) -> Expense | None:
        query = select(Expense).where(Expense.id == expense_id)
        if lock:
            query = query.with_for_update()
        return await self.session.scalar(query)

    async def list_expenses(
        self,
        company_id: UUID,
        branch_id: UUID | None,
        status: str | None,
        category_id: UUID | None,
        start_date: date | None,
        end_date: date | None,
        search: str | None,
    ) -> list[Expense]:
        query = select(Expense).where(Expense.company_id == company_id)
        if branch_id is not None:
            query = query.where(Expense.branch_id == branch_id)
        if status:
            query = query.where(Expense.status == status)
        if category_id:
            query = query.where(Expense.category_id == category_id)
        if start_date:
            query = query.where(Expense.date >= start_date)
        if end_date:
            query = query.where(Expense.date <= end_date)
        if search:
            term = f"%{search.strip()}%"
            query = query.where(
                or_(
                    Expense.expense_number.ilike(term),
                    Expense.vendor.ilike(term),
                    Expense.description.ilike(term),
                    Expense.reference.ilike(term),
                )
            )
        return list(await self.session.scalars(query.order_by(Expense.date.desc(), Expense.created_at.desc())))

