from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class NumberSequenceCreate(BaseModel):
    company_id: UUID
    branch_id: UUID | None = None
    financial_year_id: UUID | None = None
    document_type: str = Field(min_length=1, max_length=50)
    prefix: str = Field(default="", max_length=30)
    separator: str = Field(default="", max_length=5)
    next_number: int = Field(default=1, ge=1)
    number_padding: int = Field(default=4, ge=1, le=12)

    @field_validator("document_type")
    @classmethod
    def normalize_document_type(cls, value: str) -> str:
        return value.strip().lower()


class NumberSequenceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    company_id: UUID
    branch_id: UUID | None
    financial_year_id: UUID | None
    document_type: str
    prefix: str
    separator: str
    next_number: int
    number_padding: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


class NumberSequenceNextRequest(BaseModel):
    sequence_id: UUID


class NumberSequenceUpdate(BaseModel):
    prefix: str | None = Field(default=None, max_length=30)
    separator: str | None = Field(default=None, max_length=5)
    number_padding: int | None = Field(default=None, ge=1, le=12)
    is_active: bool | None = None


class GeneratedNumberRead(BaseModel):
    sequence_id: UUID
    number: int
    formatted_number: str
