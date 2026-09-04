from datetime import date as date_type
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator

STATES = ("DRAFT", "SUBMITTED", "APPROVED", "POSTED", "REJECTED", "CANCELLED")
PAYMENT_METHODS = ("cash", "bank", "card", "credit", "other")


class ExpenseCategoryCreate(BaseModel):
    company_id: UUID
    branch_id: UUID | None = None
    code: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=150)
    description: str | None = None
    is_active: bool = True

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return value.strip()


class ExpenseCategoryUpdate(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=50)
    name: str | None = Field(default=None, min_length=1, max_length=150)
    description: str | None = None
    is_active: bool | None = None


class ExpenseCategoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    company_id: UUID
    branch_id: UUID | None
    code: str
    name: str
    description: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ExpenseCreate(BaseModel):
    company_id: UUID
    branch_id: UUID | None = None
    financial_year_id: UUID
    expense_number: str | None = Field(default=None, max_length=50)
    date: date_type = Field(validation_alias=AliasChoices("date", "expense_date"))
    category_id: UUID = Field(validation_alias=AliasChoices("category_id", "category"))
    account_id: UUID = Field(validation_alias=AliasChoices("account_id", "account"))
    description: str | None = None
    vendor: str | None = Field(default=None, max_length=200)
    amount: Decimal = Field(gt=0, decimal_places=2)
    tax_amount: Decimal = Field(default=Decimal("0.00"), ge=0, decimal_places=2)
    payment_method: str = "cash"
    cash_account_id: UUID | None = None
    reference: str | None = Field(default=None, max_length=100)
    attachment: dict | list | None = None

    @field_validator("payment_method", mode="before")
    @classmethod
    def normalize_payment_method(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("expense_number", "description", "vendor", "reference", mode="before")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        return value.strip() if isinstance(value, str) else value


class ExpenseUpdate(BaseModel):
    date: date_type | None = Field(default=None, validation_alias=AliasChoices("date", "expense_date"))
    financial_year_id: UUID | None = None
    category_id: UUID | None = Field(default=None, validation_alias=AliasChoices("category_id", "category"))
    account_id: UUID | None = Field(default=None, validation_alias=AliasChoices("account_id", "account"))
    description: str | None = None
    vendor: str | None = Field(default=None, max_length=200)
    amount: Decimal | None = Field(default=None, gt=0, decimal_places=2)
    tax_amount: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    payment_method: str | None = None
    cash_account_id: UUID | None = None
    reference: str | None = Field(default=None, max_length=100)
    attachment: dict | list | None = None

    @field_validator("payment_method", mode="before")
    @classmethod
    def normalize_payment_method(cls, value: str | None) -> str | None:
        return value.strip().lower() if isinstance(value, str) else value


class ExpenseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    company_id: UUID
    branch_id: UUID | None
    financial_year_id: UUID
    expense_number: str
    date: date_type
    category_id: UUID
    account_id: UUID
    description: str | None
    vendor: str | None
    amount: Decimal
    tax_amount: Decimal
    payment_method: str
    cash_account_id: UUID | None
    reference: str | None
    attachment: dict | list | None
    status: str
    created_by: UUID | None
    approved_by: UUID | None
    posted_by: UUID | None
    approved_at: datetime | None
    posted_at: datetime | None
    rejection_reason: str | None
    cancellation_reason: str | None
    reversal_of_id: UUID | None
    correction_of_id: UUID | None
    created_at: datetime
    updated_at: datetime


class ExpenseReject(BaseModel):
    reason: str = Field(default="Rejected by approver", min_length=1, max_length=500)


class ExpenseCancel(BaseModel):
    reason: str = Field(default="Cancelled by user", min_length=1, max_length=500)


class ExpenseAttachment(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    content_type: str = Field(min_length=1, max_length=100)
    size: int = Field(ge=0)
    url: str | None = Field(default=None, max_length=1000)
    storage_key: str | None = Field(default=None, max_length=500)


class ExpenseCorrection(BaseModel):
    amount: Decimal | None = Field(default=None, gt=0, decimal_places=2)
    reason: str = Field(min_length=1, max_length=500)
