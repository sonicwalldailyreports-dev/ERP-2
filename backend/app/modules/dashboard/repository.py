from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import case, func, literal, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    Account,
    AccountType,
    Branch,
    CashAccount,
    CashOpeningBalance,
    CashTransaction,
    Expense,
    ExpenseCategory,
    FinancialYear,
    Transaction,
    TransactionLine,
    UserBranch,
)


class DashboardRepository:
    """Read-only, set-based dashboard queries.

    Every query is scoped by company and (when selected) branch.  The dashboard
    intentionally uses existing posted ledgers and master opening balances; it
    does not infer balances from records the user cannot access.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def financial_year(self, company_id: UUID, year_id: UUID | None) -> FinancialYear | None:
        query = select(FinancialYear).where(FinancialYear.company_id == company_id)
        if year_id is not None:
            query = query.where(FinancialYear.id == year_id)
        else:
            query = query.where(FinancialYear.is_active.is_(True)).order_by(FinancialYear.start_date.desc())
        return await self.session.scalar(query)

    async def branch(self, company_id: UUID, branch_id: UUID) -> Branch | None:
        return await self.session.scalar(
            select(Branch).where(Branch.id == branch_id, Branch.company_id == company_id, Branch.is_active.is_(True))
        )

    async def authorized_branch_ids(self, user_id: UUID, company_id: UUID) -> list[UUID]:
        return list(
            await self.session.scalars(
                select(UserBranch.branch_id).where(
                    UserBranch.user_id == user_id, UserBranch.company_id == company_id
                )
            )
        )

    @staticmethod
    def _scope(query, model, company_id: UUID, branch_id: UUID | None):
        query = query.where(model.company_id == company_id)
        if branch_id is not None:
            query = query.where(or_(model.branch_id == branch_id, model.branch_id.is_(None)))
        return query

    async def ledger_totals(
        self, company_id: UUID, branch_id: UUID | None, year_id: UUID, start: date, end: date
    ) -> list[tuple[date, str, Decimal]]:
        amount = case(
            (AccountType.code == "income", TransactionLine.credit - TransactionLine.debit),
            (AccountType.code == "expense", TransactionLine.debit - TransactionLine.credit),
            else_=Decimal(0),
        )
        query = (
            select(Transaction.transaction_date, AccountType.code, func.coalesce(func.sum(amount), 0))
            .join(TransactionLine, TransactionLine.transaction_id == Transaction.id)
            .join(Account, Account.id == TransactionLine.account_id)
            .join(AccountType, AccountType.id == Account.account_type_id)
            .where(
                Transaction.company_id == company_id,
                Transaction.financial_year_id == year_id,
                Transaction.status == "POSTED",
                Transaction.transaction_date.between(start, end),
                AccountType.code.in_(("income", "expense")),
            )
            .group_by(Transaction.transaction_date, AccountType.code)
        )
        if branch_id is not None:
            query = query.where(or_(Transaction.branch_id == branch_id, Transaction.branch_id.is_(None)))
        return list((await self.session.execute(query)).all())

    async def cash_totals(
        self, company_id: UUID, branch_id: UUID | None, year_id: UUID, start: date, end: date
    ) -> tuple[Decimal, Decimal, list[tuple[date, Decimal, Decimal]]]:
        accounts_query = select(CashAccount).where(
            CashAccount.company_id == company_id,
            CashAccount.deleted_at.is_(None),
            CashAccount.is_active.is_(True),
            CashAccount.branch_id.is_(None)
            if branch_id is None
            else or_(CashAccount.branch_id == branch_id, CashAccount.branch_id.is_(None)),
        )
        accounts = list(await self.session.scalars(accounts_query))
        if not accounts:
            return Decimal(0), Decimal(0), []
        account_ids = [account.id for account in accounts]
        openings = {
            row.cash_account_id: row.amount
            for row in await self.session.scalars(
                select(CashOpeningBalance).where(
                    CashOpeningBalance.company_id == company_id,
                    CashOpeningBalance.financial_year_id == year_id,
                    CashOpeningBalance.cash_account_id.in_(account_ids),
                )
            )
        }
        movement = case(
            (CashTransaction.transaction_type == "receipt", CashTransaction.amount),
            (CashTransaction.transaction_type == "transfer", CashTransaction.amount),
            else_=-CashTransaction.amount,
        )
        query = (
            select(
                CashTransaction.transaction_date,
                func.coalesce(func.sum(case((CashTransaction.transaction_type == "receipt", CashTransaction.amount), else_=0)), 0),
                func.coalesce(func.sum(case((CashTransaction.transaction_type == "payment", CashTransaction.amount), else_=0)), 0),
            )
            .where(
                CashTransaction.company_id == company_id,
                CashTransaction.financial_year_id == year_id,
                CashTransaction.state == "POSTED",
                CashTransaction.cash_account_id.in_(account_ids),
                CashTransaction.transaction_date.between(start, end),
            )
            .group_by(CashTransaction.transaction_date)
        )
        if branch_id is not None:
            query = query.where(or_(CashTransaction.branch_id == branch_id, CashTransaction.branch_id.is_(None)))
        rows = list((await self.session.execute(query)).all())
        balance_query = (
            select(CashTransaction.cash_account_id, func.coalesce(func.sum(movement), 0))
            .where(
                CashTransaction.company_id == company_id,
                CashTransaction.financial_year_id == year_id,
                CashTransaction.state == "POSTED",
                CashTransaction.cash_account_id.in_(account_ids),
                CashTransaction.transaction_date <= end,
            )
            .group_by(CashTransaction.cash_account_id)
        )
        if branch_id is not None:
            balance_query = balance_query.where(or_(CashTransaction.branch_id == branch_id, CashTransaction.branch_id.is_(None)))
        movements = dict((await self.session.execute(balance_query)).all())
        cash = bank = Decimal(0)
        for account in accounts:
            value = (openings.get(account.id, account.opening_balance) or Decimal(0)) + movements.get(account.id, 0)
            if account.name.lower().find("bank") >= 0 or account.account_code.lower().find("bank") >= 0:
                bank += value
            else:
                cash += value
        return cash, bank, rows

    async def category_totals(
        self, company_id: UUID, branch_id: UUID | None, year_id: UUID, start: date, end: date
    ):
        query = (
            select(Expense.category_id, ExpenseCategory.name, func.coalesce(func.sum(Expense.amount + Expense.tax_amount), 0))
            .join(ExpenseCategory, ExpenseCategory.id == Expense.category_id)
            .where(
                Expense.company_id == company_id,
                Expense.financial_year_id == year_id,
                Expense.status == "POSTED",
                Expense.date.between(start, end),
            )
            .group_by(Expense.category_id, ExpenseCategory.name)
            .order_by(func.sum(Expense.amount + Expense.tax_amount).desc())
        )
        if branch_id is not None:
            query = query.where(or_(Expense.branch_id == branch_id, Expense.branch_id.is_(None)))
        return list((await self.session.execute(query)).all())

    async def branch_totals(self, company_id: UUID, year_id: UUID, start: date, end: date, branch_ids: list[UUID]):
        amount = case(
            (AccountType.code == "income", TransactionLine.credit - TransactionLine.debit),
            (AccountType.code == "expense", TransactionLine.debit - TransactionLine.credit),
            else_=Decimal(0),
        )
        query = (
            select(
                Transaction.branch_id,
                AccountType.code,
                func.coalesce(func.sum(amount), 0),
            )
            .join(TransactionLine, TransactionLine.transaction_id == Transaction.id)
            .join(Account, Account.id == TransactionLine.account_id)
            .join(AccountType, AccountType.id == Account.account_type_id)
            .where(
                Transaction.company_id == company_id,
                Transaction.financial_year_id == year_id,
                Transaction.status == "POSTED",
                Transaction.transaction_date.between(start, end),
                AccountType.code.in_(("income", "expense")),
                Transaction.branch_id.in_(branch_ids),
            )
            .group_by(Transaction.branch_id, AccountType.code)
        )
        return list((await self.session.execute(query)).all())

    async def recent_transactions(self, company_id: UUID, branch_id: UUID | None, year_id: UUID, start: date, end: date, limit: int, offset: int):
        amount = func.coalesce(func.sum(TransactionLine.debit), 0)
        query = (
            select(Transaction, amount)
            .outerjoin(TransactionLine, TransactionLine.transaction_id == Transaction.id)
            .where(
                Transaction.company_id == company_id,
                Transaction.financial_year_id == year_id,
                Transaction.transaction_date.between(start, end),
            )
            .group_by(Transaction.id)
            .order_by(Transaction.transaction_date.desc(), Transaction.created_at.desc())
        )
        if branch_id is not None:
            query = query.where(or_(Transaction.branch_id == branch_id, Transaction.branch_id.is_(None)))
        total = await self.session.scalar(select(func.count()).select_from(query.subquery())) or 0
        return list((await self.session.execute(query.limit(limit).offset(offset))).all()), total

    async def pending_approvals(self, company_id: UUID, branch_id: UUID | None, year_id: UUID, start: date, end: date, limit: int, offset: int):
        exp = select(
            Expense.id.label("id"), literal("expense").label("kind"), Expense.expense_number.label("number"),
            Expense.date.label("date"), (Expense.amount + Expense.tax_amount).label("amount"),
            Expense.status.label("status"), Expense.description.label("description"),
        ).where(
            Expense.company_id == company_id, Expense.financial_year_id == year_id,
            Expense.status == "SUBMITTED", Expense.date.between(start, end),
        )
        cash = select(
            CashTransaction.id.label("id"), literal("cash").label("kind"), func.coalesce(CashTransaction.document_number, literal("cash")).label("number"),
            CashTransaction.transaction_date.label("date"), CashTransaction.amount.label("amount"),
            CashTransaction.state.label("status"), CashTransaction.description.label("description"),
        ).where(
            CashTransaction.company_id == company_id, CashTransaction.financial_year_id == year_id,
            CashTransaction.state == "SUBMITTED", CashTransaction.transaction_date.between(start, end),
        )
        if branch_id is not None:
            exp = exp.where(or_(Expense.branch_id == branch_id, Expense.branch_id.is_(None)))
            cash = cash.where(or_(CashTransaction.branch_id == branch_id, CashTransaction.branch_id.is_(None)))
        union = exp.union_all(cash).subquery()
        query = select(union).order_by(union.c.date.desc()).limit(limit).offset(offset)
        total = await self.session.scalar(select(func.count()).select_from(union)) or 0
        return list((await self.session.execute(query)).mappings()), total

    async def recent_expenses(self, company_id: UUID, branch_id: UUID | None, year_id: UUID, start: date, end: date, limit: int, offset: int):
        query = (
            select(Expense, ExpenseCategory.name)
            .join(ExpenseCategory, ExpenseCategory.id == Expense.category_id)
            .where(
                Expense.company_id == company_id, Expense.financial_year_id == year_id,
                Expense.date.between(start, end),
            )
            .order_by(Expense.date.desc(), Expense.created_at.desc())
        )
        if branch_id is not None:
            query = query.where(or_(Expense.branch_id == branch_id, Expense.branch_id.is_(None)))
        total = await self.session.scalar(select(func.count()).select_from(query.subquery())) or 0
        return list((await self.session.execute(query.limit(limit).offset(offset))).all()), total

    async def outstanding(self, model, code_field, name_field, company_id: UUID, branch_id: UUID | None, limit: int, offset: int):
        filters = [model.company_id == company_id, model.is_active.is_(True), model.deleted_at.is_(None)]
        if branch_id is not None:
            filters.append(or_(model.branch_id == branch_id, model.branch_id.is_(None)))
        query = select(model).where(*filters)
        query = query.order_by(model.opening_balance.desc(), model.name).limit(limit).offset(offset)
        rows = list(await self.session.scalars(query))
        total = await self.session.scalar(select(func.count()).select_from(model).where(*filters)) or 0
        amount = await self.session.scalar(select(func.coalesce(func.sum(model.opening_balance), 0)).where(*filters)) or Decimal(0)
        return rows, total, amount
