from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

ZERO = Decimal("0.00")


class DashboardCards(BaseModel):
    income: Decimal = ZERO
    expenses: Decimal = ZERO
    cash_balance: Decimal = ZERO
    bank_balance: Decimal = ZERO
    receivables: Decimal = ZERO
    payables: Decimal = ZERO


class DashboardPoint(BaseModel):
    period: str
    income: Decimal = ZERO
    expenses: Decimal = ZERO
    receipts: Decimal = ZERO
    payments: Decimal = ZERO
    net: Decimal = ZERO


class CategoryTotal(BaseModel):
    category_id: UUID
    category: str
    amount: Decimal


class BranchTotal(BaseModel):
    branch_id: UUID | None
    branch: str
    income: Decimal = ZERO
    expenses: Decimal = ZERO
    net: Decimal = ZERO


class DashboardTransaction(BaseModel):
    id: UUID
    transaction_number: str
    transaction_date: date
    description: str | None
    reference: str | None
    status: str
    amount: Decimal


class DashboardApproval(BaseModel):
    id: UUID
    kind: str
    number: str
    date: date
    amount: Decimal
    status: str
    description: str | None


class DashboardExpense(BaseModel):
    id: UUID
    expense_number: str
    date: date
    category: str
    vendor: str | None
    amount: Decimal
    status: str
    description: str | None


class OutstandingItem(BaseModel):
    id: UUID
    code: str
    name: str
    outstanding: Decimal
    branch_id: UUID | None


class DashboardPagination(BaseModel):
    page: int
    page_size: int
    total: int


class DashboardResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    company_id: UUID
    branch_id: UUID | None
    financial_year_id: UUID
    start_date: date
    end_date: date
    cards: DashboardCards
    income_vs_expense: list[DashboardPoint]
    cash_flow: list[DashboardPoint]
    expenses_by_category: list[CategoryTotal]
    branch_comparison: list[BranchTotal]
    recent_transactions: list[DashboardTransaction]
    pending_approvals: list[DashboardApproval]
    recent_expenses: list[DashboardExpense]
    customer_outstanding: list[OutstandingItem]
    vendor_outstanding: list[OutstandingItem]
    pagination: DashboardPagination
