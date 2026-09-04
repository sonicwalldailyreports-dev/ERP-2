from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator, model_validator

STATES = ("DRAFT", "SUBMITTED", "APPROVED", "POSTED", "REJECTED", "CANCELLED")
TRANSACTION_TYPES = ("receipt", "payment", "transfer")


class CashAccountCreate(BaseModel):
    company_id: UUID
    branch_id: UUID | None = None
    account_id: UUID | None = None
    account_code: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=150)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    opening_balance: Decimal = Field(default=Decimal("0.00"), ge=0, decimal_places=2)

    @field_validator("account_code", "currency", mode="before")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("name", mode="before")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return value.strip()


class CashAccountUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    account_id: UUID | None = None
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    is_active: bool | None = None

    @field_validator("currency", mode="before")
    @classmethod
    def normalize_currency(cls, value: str | None) -> str | None:
        return value.strip().upper() if value else value


class CashAccountRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    company_id: UUID
    branch_id: UUID | None
    account_id: UUID | None
    account_code: str
    name: str
    currency: str
    opening_balance: Decimal
    balance: Decimal = Decimal("0.00")
    is_active: bool
    deleted_at: datetime | None
    created_at: datetime
    updated_at: datetime


class OpeningBalanceCreate(BaseModel):
    cash_account_id: UUID
    financial_year_id: UUID
    amount: Decimal = Field(ge=0, decimal_places=2)
    notes: str | None = None


class OpeningBalanceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    cash_account_id: UUID
    company_id: UUID
    financial_year_id: UUID
    amount: Decimal
    notes: str | None
    created_by: UUID | None
    created_at: datetime
    updated_at: datetime


class CashTransactionCreate(BaseModel):
    company_id: UUID
    branch_id: UUID | None = None
    cash_account_id: UUID = Field(validation_alias=AliasChoices("cash_account_id", "source_cash_account_id", "from_cash_account_id", "source_account_id"))
    target_cash_account_id: UUID | None = Field(default=None, validation_alias=AliasChoices("target_cash_account_id", "destination_cash_account_id", "to_cash_account_id", "destination_account_id"))
    financial_year_id: UUID
    transaction_type: str = Field(validation_alias=AliasChoices("transaction_type", "type"))
    transaction_date: date
    amount: Decimal = Field(gt=0, decimal_places=2)
    reference: str | None = Field(default=None, max_length=100)
    description: str | None = None

    @field_validator("transaction_type", mode="before")
    @classmethod
    def normalize_type(cls, value: str) -> str:
        return value.strip().lower()

    @model_validator(mode="after")
    def validate_transfer(self) -> "CashTransactionCreate":
        if self.transaction_type not in TRANSACTION_TYPES:
            raise ValueError("transaction_type must be receipt, payment, or transfer")
        if self.transaction_type == "transfer":
            if self.target_cash_account_id is None:
                raise ValueError("target_cash_account_id is required for transfers")
            if self.target_cash_account_id == self.cash_account_id:
                raise ValueError("Transfer source and target must differ")
        elif self.target_cash_account_id is not None:
            raise ValueError("target_cash_account_id is only valid for transfers")
        return self


class CashTransactionUpdate(BaseModel):
    transaction_date: date | None = None
    amount: Decimal | None = Field(default=None, gt=0, decimal_places=2)
    reference: str | None = Field(default=None, max_length=100)
    description: str | None = None


class CashTransactionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    company_id: UUID
    branch_id: UUID | None
    cash_account_id: UUID
    target_cash_account_id: UUID | None
    financial_year_id: UUID
    transaction_type: str
    transaction_date: date
    amount: Decimal
    reference: str | None
    description: str | None
    document_number: str | None
    state: str
    rejection_reason: str | None
    cancellation_reason: str | None
    reversal_of_id: UUID | None
    created_by: UUID | None
    submitted_by: UUID | None
    approved_by: UUID | None
    posted_by: UUID | None
    reversed_by: UUID | None
    submitted_at: datetime | None
    approved_at: datetime | None
    posted_at: datetime | None
    cancelled_at: datetime | None
    reversed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class TransactionReject(BaseModel):
    reason: str = Field(default="Rejected by approver", min_length=1, max_length=500)


class TransactionCancel(BaseModel):
    reason: str = Field(default="Cancelled by user", min_length=1, max_length=500)


class DailySummaryRead(BaseModel):
    summary_date: date
    cash_account_id: UUID
    cash_account_name: str
    opening_balance: Decimal
    receipts: Decimal
    payments: Decimal
    transfers_in: Decimal
    transfers_out: Decimal
    closing_balance: Decimal
