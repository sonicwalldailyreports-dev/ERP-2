"""Set-based read queries used by reports.

Routes never build SQL.  Every public query takes an explicit company scope
and applies the optional branch predicate to all tenant-owned tables.
"""

from __future__ import annotations

from decimal import Decimal
from math import ceil
from typing import Any
from uuid import UUID

from sqlalchemy import case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    Account,
    AccountType,
    Branch,
    CashAccount,
    CashTransaction,
    Customer,
    Expense,
    ExpenseCategory,
    FinancialYear,
    Transaction,
    TransactionLine,
    User,
    Vendor,
)
from app.modules.reports.schemas import ReportFilters, ReportType


class ReportRepository:
    """Read-only repository for synchronous and future queued report jobs."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def company_exists(self, company_id: UUID) -> bool:
        from app.db.models import Company

        return (await self.session.scalar(select(Company.id).where(Company.id == company_id))) is not None

    async def branch_exists(self, company_id: UUID, branch_id: UUID) -> bool:
        return (
            await self.session.scalar(
                select(Branch.id).where(
                    Branch.id == branch_id,
                    Branch.company_id == company_id,
                    Branch.is_active.is_(True),
                )
            )
        ) is not None

    async def financial_year(self, company_id: UUID, year_id: UUID | None) -> FinancialYear | None:
        query = select(FinancialYear).where(FinancialYear.company_id == company_id)
        if year_id is not None:
            query = query.where(FinancialYear.id == year_id)
        else:
            query = query.where(FinancialYear.is_active.is_(True)).order_by(FinancialYear.start_date.desc())
        return await self.session.scalar(query)

    @staticmethod
    def _branch_scope(query, model, branch_id: UUID | None):
        if branch_id is not None:
            query = query.where(or_(model.branch_id == branch_id, model.branch_id.is_(None)))
        return query

    @staticmethod
    def _page(page: int, page_size: int, total: int) -> tuple[int, int, int]:
        pages = ceil(total / page_size) if total else 0
        return (page - 1) * page_size, pages, total

    async def _result(
        self,
        query,
        count_query,
        page: int,
        page_size: int,
        totals: dict[str, Decimal] | None = None,
    ) -> tuple[list[dict[str, Any]], int, dict[str, Decimal], int]:
        total = int(await self.session.scalar(count_query) or 0)
        offset, pages, _ = self._page(page, page_size, total)
        result = await self.session.execute(query.limit(page_size).offset(offset))
        return [dict(row) for row in result.mappings()], total, totals or {}, pages

    async def cash_transactions(
        self, filters: ReportFilters, page: int, page_size: int
    ) -> tuple[list[dict[str, Any]], int, dict[str, Decimal], int]:
        predicates = [
            CashTransaction.company_id == filters.company_id,
            CashTransaction.transaction_date.between(filters.start_date, filters.end_date),
        ]
        if filters.branch_id is not None:
            predicates.append(or_(CashTransaction.branch_id == filters.branch_id, CashTransaction.branch_id.is_(None)))
        if filters.financial_year_id:
            predicates.append(CashTransaction.financial_year_id == filters.financial_year_id)
        if filters.account_id:
            predicates.append(
                or_(
                    CashTransaction.cash_account_id == filters.account_id,
                    CashTransaction.target_cash_account_id == filters.account_id,
                )
            )
        if filters.status:
            predicates.append(CashTransaction.state == filters.status.upper())
        query = (
            select(
                CashTransaction.id,
                CashTransaction.transaction_date,
                CashTransaction.document_number,
                CashTransaction.transaction_type,
                CashTransaction.cash_account_id,
                CashTransaction.target_cash_account_id,
                CashTransaction.amount,
                CashTransaction.reference,
                CashTransaction.description,
                CashTransaction.state.label("status"),
            )
            .where(*predicates)
            .order_by(CashTransaction.transaction_date.desc(), CashTransaction.created_at.desc())
        )
        count = select(func.count()).select_from(CashTransaction).where(*predicates)
        aggregate = await self.session.execute(
            select(
                func.coalesce(func.sum(case((CashTransaction.transaction_type == "receipt", CashTransaction.amount), else_=0)), 0).label("receipts"),
                func.coalesce(func.sum(case((CashTransaction.transaction_type == "payment", CashTransaction.amount), else_=0)), 0).label("payments"),
                func.coalesce(func.sum(case((CashTransaction.transaction_type == "transfer", CashTransaction.amount), else_=0)), 0).label("transfers"),
            ).where(*predicates)
        )
        values = aggregate.one()
        totals = {key: Decimal(value or 0) for key, value in values._mapping.items()}
        return await self._result(query, count, page, page_size, totals)

    async def cash_daily_book(
        self, filters: ReportFilters, page: int, page_size: int
    ) -> tuple[list[dict[str, Any]], int, dict[str, Decimal], int]:
        predicates = [
            CashTransaction.company_id == filters.company_id,
            CashTransaction.state == "POSTED",
            CashTransaction.transaction_date.between(filters.start_date, filters.end_date),
        ]
        if filters.branch_id is not None:
            predicates.append(or_(CashTransaction.branch_id == filters.branch_id, CashTransaction.branch_id.is_(None)))
        if filters.financial_year_id:
            predicates.append(CashTransaction.financial_year_id == filters.financial_year_id)
        if filters.account_id:
            predicates.append(CashTransaction.cash_account_id == filters.account_id)
        grouped = (
            select(
                CashTransaction.transaction_date.label("date"),
                CashTransaction.cash_account_id,
                CashAccount.name.label("account"),
                func.coalesce(func.sum(case((CashTransaction.transaction_type == "receipt", CashTransaction.amount), else_=0)), 0).label("receipts"),
                func.coalesce(func.sum(case((CashTransaction.transaction_type == "payment", CashTransaction.amount), else_=0)), 0).label("payments"),
                func.coalesce(func.sum(case((CashTransaction.transaction_type == "transfer", CashTransaction.amount), else_=0)), 0).label("transfers"),
            )
            .join(CashAccount, CashAccount.id == CashTransaction.cash_account_id)
            .where(*predicates)
            .group_by(CashTransaction.transaction_date, CashTransaction.cash_account_id, CashAccount.name)
            .order_by(CashTransaction.transaction_date.desc(), CashAccount.name)
        )
        subquery = grouped.subquery()
        count = select(func.count()).select_from(subquery)
        aggregate = await self.session.execute(
            select(
                func.coalesce(func.sum(subquery.c.receipts), 0).label("receipts"),
                func.coalesce(func.sum(subquery.c.payments), 0).label("payments"),
                func.coalesce(func.sum(subquery.c.transfers), 0).label("transfers"),
            )
        )
        totals = {key: Decimal(value or 0) for key, value in aggregate.one()._mapping.items()}
        return await self._result(grouped, count, page, page_size, totals)

    async def cash_summary(
        self, filters: ReportFilters, page: int, page_size: int
    ) -> tuple[list[dict[str, Any]], int, dict[str, Decimal], int]:
        predicates = [
            CashTransaction.company_id == filters.company_id,
            CashTransaction.state == "POSTED",
            CashTransaction.transaction_date.between(filters.start_date, filters.end_date),
        ]
        if filters.branch_id is not None:
            predicates.append(or_(CashTransaction.branch_id == filters.branch_id, CashTransaction.branch_id.is_(None)))
        if filters.financial_year_id:
            predicates.append(CashTransaction.financial_year_id == filters.financial_year_id)
        if filters.account_id:
            predicates.append(CashTransaction.cash_account_id == filters.account_id)
        amount = func.coalesce(func.sum(CashTransaction.amount), 0)
        query = (
            select(
                CashTransaction.cash_account_id,
                CashAccount.name.label("account"),
                func.coalesce(func.sum(case((CashTransaction.transaction_type == "receipt", CashTransaction.amount), else_=0)), 0).label("receipts"),
                func.coalesce(func.sum(case((CashTransaction.transaction_type == "payment", CashTransaction.amount), else_=0)), 0).label("payments"),
                func.coalesce(func.sum(case((CashTransaction.transaction_type == "transfer", CashTransaction.amount), else_=0)), 0).label("transfers"),
            )
            .join(CashAccount, CashAccount.id == CashTransaction.cash_account_id)
            .where(*predicates)
            .group_by(CashTransaction.cash_account_id, CashAccount.name)
            .order_by(amount.desc(), CashAccount.name)
        )
        subquery = query.subquery()
        count = select(func.count()).select_from(subquery)
        aggregate = await self.session.execute(
            select(
                func.coalesce(func.sum(subquery.c.receipts), 0).label("receipts"),
                func.coalesce(func.sum(subquery.c.payments), 0).label("payments"),
                func.coalesce(func.sum(subquery.c.transfers), 0).label("transfers"),
            )
        )
        totals = {key: Decimal(value or 0) for key, value in aggregate.one()._mapping.items()}
        return await self._result(query, count, page, page_size, totals)

    async def cash_closing(
        self, filters: ReportFilters, page: int, page_size: int
    ) -> tuple[list[dict[str, Any]], int, dict[str, Decimal], int]:
        accounts_query = select(CashAccount).where(
            CashAccount.company_id == filters.company_id,
            CashAccount.deleted_at.is_(None),
            CashAccount.is_active.is_(True),
        )
        if filters.branch_id is not None:
            accounts_query = accounts_query.where(or_(CashAccount.branch_id == filters.branch_id, CashAccount.branch_id.is_(None)))
        if filters.account_id:
            accounts_query = accounts_query.where(CashAccount.id == filters.account_id)
        accounts = list(await self.session.scalars(accounts_query.order_by(CashAccount.name)))
        account_ids = [account.id for account in accounts]
        if not account_ids:
            return [], 0, {"closing_balance": Decimal(0)}, 0
        movement = case(
            (CashTransaction.transaction_type.in_(("receipt", "transfer")), CashTransaction.amount),
            else_=-CashTransaction.amount,
        )
        predicates = [
            CashTransaction.company_id == filters.company_id,
            CashTransaction.state == "POSTED",
            CashTransaction.cash_account_id.in_(account_ids),
            CashTransaction.transaction_date <= filters.end_date,
        ]
        if filters.financial_year_id:
            predicates.append(CashTransaction.financial_year_id == filters.financial_year_id)
        if filters.branch_id is not None:
            predicates.append(or_(CashTransaction.branch_id == filters.branch_id, CashTransaction.branch_id.is_(None)))
        movement_rows = {
            row.cash_account_id: row.total
            for row in (
                await self.session.execute(
                    select(CashTransaction.cash_account_id, func.coalesce(func.sum(movement), 0).label("total"))
                    .where(*predicates)
                    .group_by(CashTransaction.cash_account_id)
                )
            ).all()
        }
        rows = [
            {
                "cash_account_id": account.id,
                "account": account.name,
                "opening_balance": account.opening_balance or Decimal(0),
                "closing_balance": (account.opening_balance or Decimal(0)) + (movement_rows.get(account.id) or Decimal(0)),
            }
            for account in accounts
        ]
        total = len(rows)
        offset, pages, _ = self._page(page, page_size, total)
        closing = sum((row["closing_balance"] for row in rows), Decimal(0))
        return rows[offset : offset + page_size], total, {"closing_balance": closing}, pages

    async def expense_report(
        self, report_type: ReportType, filters: ReportFilters, page: int, page_size: int
    ) -> tuple[list[dict[str, Any]], int, dict[str, Decimal], int]:
        predicates = [
            Expense.company_id == filters.company_id,
            Expense.date.between(filters.start_date, filters.end_date),
        ]
        if filters.branch_id is not None:
            predicates.append(or_(Expense.branch_id == filters.branch_id, Expense.branch_id.is_(None)))
        if filters.financial_year_id:
            predicates.append(Expense.financial_year_id == filters.financial_year_id)
        if filters.category_id:
            predicates.append(Expense.category_id == filters.category_id)
        if filters.account_id:
            predicates.append(Expense.account_id == filters.account_id)
        if filters.user_id:
            predicates.append(Expense.created_by == filters.user_id)
        if filters.status:
            predicates.append(Expense.status == filters.status.upper())
        amount = func.coalesce(func.sum(Expense.amount + Expense.tax_amount), 0)
        if report_type == ReportType.EXPENSES_BY_CATEGORY:
            key_columns = [Expense.category_id, ExpenseCategory.name.label("category")]
            group_columns = [Expense.category_id, ExpenseCategory.name]
            order_column = amount.desc()
        elif report_type == ReportType.EXPENSES_BY_BRANCH:
            key_columns = [Expense.branch_id, Branch.name.label("branch")]
            group_columns = [Expense.branch_id, Branch.name]
            order_column = amount.desc()
        elif report_type == ReportType.EXPENSES_BY_USER:
            key_columns = [Expense.created_by.label("user_id"), User.full_name.label("user")]
            group_columns = [Expense.created_by, User.full_name]
            order_column = amount.desc()
        else:
            key_columns = [Expense.date.label("date")]
            group_columns = [Expense.date]
            order_column = Expense.date.desc()
        query = select(*key_columns, amount.label("amount"), func.count(Expense.id).label("count")).where(*predicates)
        if report_type == ReportType.EXPENSES_BY_CATEGORY:
            query = query.join(ExpenseCategory, ExpenseCategory.id == Expense.category_id)
        elif report_type == ReportType.EXPENSES_BY_BRANCH:
            query = query.outerjoin(Branch, Branch.id == Expense.branch_id)
        elif report_type == ReportType.EXPENSES_BY_USER:
            query = query.outerjoin(User, User.id == Expense.created_by)
        query = query.group_by(*group_columns).order_by(order_column)
        subquery = query.subquery()
        count = select(func.count()).select_from(subquery)
        aggregate = await self.session.scalar(select(func.coalesce(func.sum(subquery.c.amount), 0))) or Decimal(0)
        return await self._result(query, count, page, page_size, {"amount": Decimal(aggregate)})

    async def _ledger_report(
        self, filters: ReportFilters, page: int, page_size: int, account_type: str | None = None
    ) -> tuple[list[dict[str, Any]], int, dict[str, Decimal], int]:
        predicates = [
            Transaction.company_id == filters.company_id,
            Transaction.status == "POSTED",
            Transaction.transaction_date.between(filters.start_date, filters.end_date),
        ]
        if filters.branch_id is not None:
            predicates.append(or_(Transaction.branch_id == filters.branch_id, Transaction.branch_id.is_(None)))
        if filters.financial_year_id:
            predicates.append(Transaction.financial_year_id == filters.financial_year_id)
        if filters.account_id:
            predicates.append(TransactionLine.account_id == filters.account_id)
        if filters.status:
            predicates.append(Transaction.status == filters.status.upper())
        amount = func.coalesce(func.sum(TransactionLine.debit), 0).label("debit")
        credit = func.coalesce(func.sum(TransactionLine.credit), 0).label("credit")
        query = (
            select(
                Transaction.id,
                Transaction.transaction_date.label("date"),
                Transaction.transaction_number,
                Transaction.reference,
                Transaction.description,
                Account.id.label("account_id"),
                Account.account_code.label("account_code"),
                Account.name.label("account"),
                amount,
                credit,
            )
            .join(TransactionLine, TransactionLine.transaction_id == Transaction.id)
            .join(Account, Account.id == TransactionLine.account_id)
            .join(AccountType, AccountType.id == Account.account_type_id)
            .where(*predicates)
        )
        if account_type:
            query = query.where(AccountType.code == account_type)
        query = query.group_by(
            Transaction.id,
            Transaction.transaction_date,
            Transaction.transaction_number,
            Transaction.reference,
            Transaction.description,
            Account.id,
            Account.account_code,
            Account.name,
        ).order_by(Transaction.transaction_date.desc(), Transaction.transaction_number)
        subquery = query.subquery()
        count = select(func.count()).select_from(subquery)
        aggregate = await self.session.execute(
            select(
                func.coalesce(func.sum(subquery.c.debit), 0).label("debit"),
                func.coalesce(func.sum(subquery.c.credit), 0).label("credit"),
            )
        )
        totals = {key: Decimal(value or 0) for key, value in aggregate.one()._mapping.items()}
        return await self._result(query, count, page, page_size, totals)

    async def management_report(
        self, report_type: ReportType, filters: ReportFilters, page: int, page_size: int
    ) -> tuple[list[dict[str, Any]], int, dict[str, Decimal], int]:
        """Return income/expense aggregates from posted general-ledger lines."""
        predicates = [
            Transaction.company_id == filters.company_id,
            Transaction.status == "POSTED",
            Transaction.transaction_date.between(filters.start_date, filters.end_date),
            AccountType.code.in_(("income", "expense")),
        ]
        if filters.branch_id is not None:
            predicates.append(or_(Transaction.branch_id == filters.branch_id, Transaction.branch_id.is_(None)))
        if filters.financial_year_id:
            predicates.append(Transaction.financial_year_id == filters.financial_year_id)
        if filters.account_id:
            predicates.append(TransactionLine.account_id == filters.account_id)
        income = case(
            (AccountType.code == "income", TransactionLine.credit - TransactionLine.debit),
            else_=0,
        )
        expense = case(
            (AccountType.code == "expense", TransactionLine.debit - TransactionLine.credit),
            else_=0,
        )
        if report_type == ReportType.MANAGEMENT_BRANCH_COMPARISON:
            key = [Transaction.branch_id, Branch.name.label("branch")]
            groups = [Transaction.branch_id, Branch.name]
            query = (
                select(
                    *key,
                    func.coalesce(func.sum(income), 0).label("income"),
                    func.coalesce(func.sum(expense), 0).label("expense"),
                )
                .select_from(Transaction)
                .outerjoin(Branch, Branch.id == Transaction.branch_id)
                .join(TransactionLine, TransactionLine.transaction_id == Transaction.id)
                .join(Account, Account.id == TransactionLine.account_id)
                .join(AccountType, AccountType.id == Account.account_type_id)
                .where(*predicates)
                .group_by(*groups)
                .order_by(Branch.name)
            )
        elif report_type == ReportType.MANAGEMENT_MONTHLY_SUMMARY:
            dialect_name = self.session.bind.dialect.name if self.session.bind is not None else "sqlite"
            period_expression = (
                func.strftime("%Y-%m", Transaction.transaction_date)
                if dialect_name == "sqlite"
                else func.to_char(Transaction.transaction_date, "YYYY-MM")
            )
            period = period_expression.label("period")
            query = (
                select(
                    period,
                    func.coalesce(func.sum(income), 0).label("income"),
                    func.coalesce(func.sum(expense), 0).label("expense"),
                )
                .select_from(Transaction)
                .join(TransactionLine, TransactionLine.transaction_id == Transaction.id)
                .join(Account, Account.id == TransactionLine.account_id)
                .join(AccountType, AccountType.id == Account.account_type_id)
                .where(*predicates)
                .group_by(period)
                .order_by(period)
            )
        else:
            query = (
                select(
                    func.coalesce(func.sum(income), 0).label("income"),
                    func.coalesce(func.sum(expense), 0).label("expense"),
                )
                .select_from(Transaction)
                .join(TransactionLine, TransactionLine.transaction_id == Transaction.id)
                .join(Account, Account.id == TransactionLine.account_id)
                .join(AccountType, AccountType.id == Account.account_type_id)
                .where(*predicates)
            )
            if report_type == ReportType.MANAGEMENT_FINANCIAL_SUMMARY:
                query = query.group_by()
        subquery = query.subquery()
        count = select(func.count()).select_from(subquery)
        aggregate_query = select(
            func.coalesce(func.sum(subquery.c.income), 0).label("income"),
            func.coalesce(func.sum(subquery.c.expense), 0).label("expense"),
        )
        aggregate = await self.session.execute(aggregate_query)
        totals = {key: Decimal(value or 0) for key, value in aggregate.one()._mapping.items()}
        totals["net"] = totals.get("income", Decimal(0)) - totals.get("expense", Decimal(0))
        result, total, _, pages = await self._result(query, count, page, page_size, totals)
        for row in result:
            if "income" in row and "expense" in row:
                row["net"] = (row["income"] or Decimal(0)) - (row["expense"] or Decimal(0))
        return result, total, totals, pages

    async def master_report(
        self, model, filters: ReportFilters, page: int, page_size: int, statement: bool
    ) -> tuple[list[dict[str, Any]], int, dict[str, Decimal], int]:
        predicates = [
            model.company_id == filters.company_id,
            model.deleted_at.is_(None),
            model.is_active.is_(True),
        ]
        if filters.branch_id is not None:
            predicates.append(or_(model.branch_id == filters.branch_id, model.branch_id.is_(None)))
        target_id = filters.customer_id if model is Customer else filters.vendor_id
        if target_id:
            predicates.append(model.id == target_id)
        query = select(model.id, model.branch_id, model.name, model.opening_balance).where(*predicates).order_by(model.name)
        count = select(func.count()).select_from(model).where(*predicates)
        opening = await self.session.scalar(select(func.coalesce(func.sum(model.opening_balance), 0)).where(*predicates)) or Decimal(0)
        if statement:
            query = query.add_columns(model.opening_balance.label("opening"))
        return await self._result(query, count, page, page_size, {"opening_balance": Decimal(opening)})

    async def fetch(
        self, report_type: ReportType, filters: ReportFilters, page: int, page_size: int
    ) -> tuple[list[dict[str, Any]], int, dict[str, Decimal], int]:
        if report_type == ReportType.CASH_TRANSACTIONS:
            return await self.cash_transactions(filters, page, page_size)
        if report_type == ReportType.CASH_DAILY_BOOK:
            return await self.cash_daily_book(filters, page, page_size)
        if report_type == ReportType.CASH_SUMMARY:
            return await self.cash_summary(filters, page, page_size)
        if report_type == ReportType.CASH_CLOSING:
            return await self.cash_closing(filters, page, page_size)
        if report_type in {
            ReportType.EXPENSES_BY_CATEGORY,
            ReportType.EXPENSES_BY_BRANCH,
            ReportType.EXPENSES_BY_USER,
            ReportType.EXPENSES_BY_DATE,
        }:
            return await self.expense_report(report_type, filters, page, page_size)
        if report_type in {ReportType.CUSTOMER_OUTSTANDING, ReportType.CUSTOMER_STATEMENT}:
            return await self.master_report(Customer, filters, page, page_size, report_type == ReportType.CUSTOMER_STATEMENT)
        if report_type in {ReportType.VENDOR_OUTSTANDING, ReportType.VENDOR_STATEMENT}:
            return await self.master_report(Vendor, filters, page, page_size, report_type == ReportType.VENDOR_STATEMENT)
        if report_type == ReportType.CUSTOMER_TRANSACTIONS:
            return await self._ledger_report(filters, page, page_size, "customer")
        if report_type == ReportType.VENDOR_TRANSACTIONS:
            return await self._ledger_report(filters, page, page_size, "vendor")
        if report_type in {
            ReportType.MANAGEMENT_INCOME_VS_EXPENSE,
            ReportType.MANAGEMENT_MONTHLY_SUMMARY,
            ReportType.MANAGEMENT_BRANCH_COMPARISON,
            ReportType.MANAGEMENT_FINANCIAL_SUMMARY,
        }:
            return await self.management_report(report_type, filters, page, page_size)
        return await self._ledger_report(filters, page, page_size)
