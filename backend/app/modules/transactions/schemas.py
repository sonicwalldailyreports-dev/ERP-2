from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


class TransactionLineCreate(BaseModel):
    account_id: UUID
    debit: Decimal = Field(default=Decimal("0.00"), ge=0, decimal_places=2)
    credit: Decimal = Field(default=Decimal("0.00"), ge=0, decimal_places=2)
    description: str | None = None


class TransactionCreate(BaseModel):
    company_id: UUID
    branch_id: UUID | None = None
    financial_year_id: UUID
    transaction_date: date
    transaction_number: str | None = Field(
        default=None,
        max_length=80,
        validation_alias=AliasChoices("transaction_number", "number", "document_number"),
    )
    reference: str | None = Field(default=None, max_length=200)
    source_module: str | None = Field(default=None, max_length=80)
    source_document: str | None = Field(default=None, max_length=120)
    description: str | None = None
    lines: list[TransactionLineCreate] = Field(min_length=2)


class TransactionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    company_id: UUID
    branch_id: UUID | None
    financial_year_id: UUID
    transaction_number: str
    transaction_date: date
    reference: str | None
    source_module: str | None
    source_document: str | None
    description: str | None
    status: str
    created_by: UUID | None
    posted_by: UUID | None
    posted_at: datetime | None
    reversed_by: UUID | None
    reversed_at: datetime | None
    reversal_of_id: UUID | None
    created_at: datetime
    updated_at: datetime
    lines: list[TransactionLineRead] = []


class TransactionLineRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    company_id: UUID
    transaction_id: UUID
    account_id: UUID
    line_number: int
    description: str | None
    debit: Decimal
    credit: Decimal


class TransactionReverse(BaseModel):
    reference: str | None = Field(default=None, max_length=200)
    description: str | None = None


# Compatibility aliases for callers that use the more explicit name.
FinancialTransactionCreate = TransactionCreate
FinancialTransactionLineCreate = TransactionLineCreate
FinancialTransactionRead = TransactionRead
