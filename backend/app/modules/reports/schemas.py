"""Schemas shared by the reporting API and export adapters.

Reports intentionally use a small, stable envelope.  Individual report rows
are dictionaries because new columns can be added without breaking clients.
"""

from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ReportType(StrEnum):
    CASH_DAILY_BOOK = "cash-daily-book"
    CASH_SUMMARY = "cash-summary"
    CASH_TRANSACTIONS = "cash-transactions"
    CASH_CLOSING = "cash-closing"
    CUSTOMER_STATEMENT = "customer-statement"
    CUSTOMER_OUTSTANDING = "customer-outstanding"
    CUSTOMER_TRANSACTIONS = "customer-transactions"
    VENDOR_STATEMENT = "vendor-statement"
    VENDOR_OUTSTANDING = "vendor-outstanding"
    VENDOR_TRANSACTIONS = "vendor-transactions"
    EXPENSES_BY_CATEGORY = "expenses-by-category"
    EXPENSES_BY_BRANCH = "expenses-by-branch"
    EXPENSES_BY_USER = "expenses-by-user"
    EXPENSES_BY_DATE = "expenses-by-date"
    MANAGEMENT_INCOME_VS_EXPENSE = "management-income-vs-expense"
    MANAGEMENT_MONTHLY_SUMMARY = "management-monthly-summary"
    MANAGEMENT_BRANCH_COMPARISON = "management-branch-comparison"
    MANAGEMENT_FINANCIAL_SUMMARY = "management-financial-summary"

    @classmethod
    def parse(cls, value: str) -> "ReportType":
        """Accept API-friendly underscores as well as canonical hyphen names."""
        try:
            return cls(value.lower().replace("_", "-"))
        except ValueError:
            raise ValueError(f"Unsupported report type: {value}") from None


class ExportFormat(StrEnum):
    CSV = "csv"
    XLSX = "xlsx"
    PDF = "pdf"


class ReportFilters(BaseModel):
    model_config = ConfigDict(extra="ignore")

    company_id: UUID
    branch_id: UUID | None = None
    financial_year_id: UUID | None = None
    start_date: date | None = None
    end_date: date | None = None
    account_id: UUID | None = None
    customer_id: UUID | None = None
    vendor_id: UUID | None = None
    category_id: UUID | None = None
    status: str | None = None
    user_id: UUID | None = None

    @model_validator(mode="after")
    def validate_dates(self) -> "ReportFilters":
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValueError("start_date must be on or before end_date")
        return self


class ReportPage(BaseModel):
    report_type: ReportType
    company_id: UUID
    branch_id: UUID | None = None
    financial_year_id: UUID | None = None
    start_date: date | None = None
    end_date: date | None = None
    items: list[dict[str, Any]] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 50
    pages: int = 0
    totals: dict[str, Decimal] = Field(default_factory=dict)


class ReportJob(BaseModel):
    """Future background-job contract.

    The current API executes small reports synchronously.  Keeping the request
    and status shape separate makes it possible to move large exports to a
    worker without changing report filters.
    """

    id: UUID
    report_type: ReportType
    status: str = "queued"
    download_url: str | None = None
