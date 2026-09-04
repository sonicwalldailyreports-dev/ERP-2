from collections import defaultdict
from datetime import date
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select

from app.db.models import Branch, Customer, Vendor
from app.modules.dashboard.repository import DashboardRepository
from app.modules.dashboard.schemas import (
    BranchTotal,
    CategoryTotal,
    DashboardApproval,
    DashboardCards,
    DashboardExpense,
    DashboardPagination,
    DashboardPoint,
    DashboardResponse,
    DashboardTransaction,
    OutstandingItem,
)


class DashboardService:
    def __init__(self, repository: DashboardRepository):
        self.repository = repository

    async def build(
        self,
        *,
        user_id: UUID,
        company_id: UUID,
        branch_id: UUID | None,
        financial_year_id: UUID | None,
        start_date: date | None,
        end_date: date | None,
        page: int,
        page_size: int,
        is_dev_context: bool,
    ) -> DashboardResponse:
        year = await self.repository.financial_year(company_id, financial_year_id)
        if year is None:
            raise HTTPException(status_code=404, detail="Financial year not found.")
        if branch_id is not None and not is_dev_context and branch_id not in await self.repository.authorized_branch_ids(user_id, company_id):
            raise HTTPException(status_code=403, detail="Branch scope is not allowed.")
        start = start_date or year.start_date
        end = end_date or year.end_date
        if start < year.start_date or end > year.end_date or start > end:
            raise HTTPException(status_code=422, detail="Date range must be within the selected financial year.")

        ledger = await self.repository.ledger_totals(company_id, branch_id, year.id, start, end)
        income_by_day: dict[date, Decimal] = defaultdict(Decimal)
        expenses_by_day: dict[date, Decimal] = defaultdict(Decimal)
        income = Decimal(0)
        expenses = Decimal(0)
        for day, kind, value in ledger:
            value = value or Decimal(0)
            if kind == "income":
                income_by_day[day] += value
                income += value
            else:
                expenses_by_day[day] += value
                expenses += value

        cash, bank, cash_rows = await self.repository.cash_totals(company_id, branch_id, year.id, start, end)
        cash_by_month: dict[str, list[Decimal]] = defaultdict(lambda: [Decimal(0), Decimal(0)])
        for day, receipts, payments in cash_rows:
            cash_by_month[day.strftime("%Y-%m")][0] += receipts or Decimal(0)
            cash_by_month[day.strftime("%Y-%m")][1] += payments or Decimal(0)
        cash_flow = [
            DashboardPoint(period=period, receipts=values[0], payments=values[1], net=values[0] - values[1])
            for period, values in sorted(cash_by_month.items())
        ]
        income_by_month: dict[str, list[Decimal]] = defaultdict(lambda: [Decimal(0), Decimal(0)])
        for day, value in income_by_day.items():
            income_by_month[day.strftime("%Y-%m")][0] += value
        for day, value in expenses_by_day.items():
            income_by_month[day.strftime("%Y-%m")][1] += value
        periods = sorted(income_by_month)
        income_chart = [
            DashboardPoint(
                period=period,
                income=values[0],
                expenses=values[1],
                net=values[0] - values[1],
            )
            for period in periods
            for values in [income_by_month[period]]
        ]

        category_rows = await self.repository.category_totals(company_id, branch_id, year.id, start, end)
        categories = [CategoryTotal(category_id=row[0], category=row[1], amount=row[2] or 0) for row in category_rows]

        branch_ids = await self.repository.authorized_branch_ids(user_id, company_id) if not is_dev_context else []
        if not branch_ids:
            branch_ids = list(
                await self.repository.session.scalars(
                    select(Branch.id).where(Branch.company_id == company_id, Branch.is_active.is_(True))
                )
            )
        branch_rows = await self.repository.branch_totals(company_id, year.id, start, end, branch_ids) if branch_ids else []
        branch_names = {}
        for branch in await self.repository.session.scalars(select(Branch).where(Branch.id.in_(branch_ids))):
            branch_names[branch.id] = branch.name
        branch_values: dict[UUID, dict[str, Decimal]] = defaultdict(lambda: defaultdict(Decimal))
        for branch_value, kind, value in branch_rows:
            branch_values[branch_value][kind] += value or Decimal(0)
        branch_chart = [
            BranchTotal(
                branch_id=branch_value,
                branch=branch_names.get(branch_value, "Branch"),
                income=values.get("income", 0),
                expenses=values.get("expense", 0),
                net=values.get("income", 0) - values.get("expense", 0),
            )
            for branch_value, values in branch_values.items()
        ]

        offset = (page - 1) * page_size
        transaction_rows, transaction_total = await self.repository.recent_transactions(
            company_id, branch_id, year.id, start, end, page_size, offset
        )
        transactions = [
            DashboardTransaction(
                id=row[0].id,
                transaction_number=row[0].transaction_number,
                transaction_date=row[0].transaction_date,
                description=row[0].description,
                reference=row[0].reference,
                status=row[0].status,
                amount=row[1] or 0,
            )
            for row in transaction_rows
        ]
        approval_rows, approval_total = await self.repository.pending_approvals(
            company_id, branch_id, year.id, start, end, page_size, offset
        )
        approvals = [DashboardApproval(**dict(row)) for row in approval_rows]
        expense_rows, expense_total = await self.repository.recent_expenses(
            company_id, branch_id, year.id, start, end, page_size, offset
        )
        recent_expenses = [
            DashboardExpense(
                id=expense.id,
                expense_number=expense.expense_number,
                date=expense.date,
                category=category,
                vendor=expense.vendor,
                amount=expense.amount + expense.tax_amount,
                status=expense.status,
                description=expense.description,
            )
            for expense, category in expense_rows
        ]
        customer_rows, customer_total, receivables = await self.repository.outstanding(
            Customer, "customer_code", "name",
            company_id, branch_id, page_size, offset,
        )
        vendor_rows, vendor_total, payables = await self.repository.outstanding(
            Vendor, "vendor_code", "name",
            company_id, branch_id, page_size, offset,
        )
        customers = [
            OutstandingItem(id=row.id, code=row.customer_code, name=row.name, outstanding=row.opening_balance, branch_id=row.branch_id)
            for row in customer_rows
        ]
        vendors = [
            OutstandingItem(id=row.id, code=row.vendor_code, name=row.name, outstanding=row.opening_balance, branch_id=row.branch_id)
            for row in vendor_rows
        ]
        return DashboardResponse(
            company_id=company_id,
            branch_id=branch_id,
            financial_year_id=year.id,
            start_date=start,
            end_date=end,
            cards=DashboardCards(
                income=income, expenses=expenses, cash_balance=cash, bank_balance=bank,
                receivables=receivables,
                payables=payables,
            ),
            income_vs_expense=income_chart,
            cash_flow=cash_flow,
            expenses_by_category=categories,
            branch_comparison=branch_chart,
            recent_transactions=transactions,
            pending_approvals=approvals,
            recent_expenses=recent_expenses,
            customer_outstanding=customers,
            vendor_outstanding=vendors,
            pagination=DashboardPagination(page=page, page_size=page_size, total=max(transaction_total, approval_total, expense_total, customer_total, vendor_total)),
        )
