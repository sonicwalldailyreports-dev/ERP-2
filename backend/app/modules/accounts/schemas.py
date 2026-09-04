from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

ACCOUNT_TYPE_CODES = (
    "cash",
    "bank",
    "customer",
    "vendor",
    "income",
    "expense",
    "asset",
    "liability",
    "equity",
)


class AccountTypeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    company_id: UUID | None
    code: str
    name: str
    description: str | None
    is_system: bool
    is_active: bool


class AccountCreate(BaseModel):
    company_id: UUID
    branch_id: UUID | None = None
    account_code: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=150)
    account_type_id: UUID
    parent_account_id: UUID | None = None
    is_group: bool = False
    is_system: bool = False
    is_default: bool = False
    description: str | None = None

    @field_validator("account_code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return value.strip()


class AccountUpdate(BaseModel):
    branch_id: UUID | None = None
    account_code: str | None = Field(default=None, min_length=1, max_length=50)
    name: str | None = Field(default=None, min_length=1, max_length=150)
    account_type_id: UUID | None = None
    parent_account_id: UUID | None = None
    is_group: bool | None = None
    is_default: bool | None = None
    description: str | None = None
    is_active: bool | None = None

    @field_validator("account_code")
    @classmethod
    def normalize_code(cls, value: str | None) -> str | None:
        return value.strip().upper() if value is not None else None

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None


class AccountRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    company_id: UUID
    branch_id: UUID | None
    account_code: str
    name: str
    account_type_id: UUID
    parent_account_id: UUID | None
    is_group: bool
    is_active: bool
    is_system: bool
    is_default: bool
    description: str | None
    deleted_at: datetime | None
    created_at: datetime
    updated_at: datetime

