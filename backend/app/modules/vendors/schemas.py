from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class VendorCreate(BaseModel):
    vendor_code: str = Field(min_length=1, max_length=50)
    name: str | None = Field(default=None, min_length=1, max_length=150)
    vendor_name: str | None = Field(default=None, max_length=150)
    address: str | None = Field(default=None, max_length=200)
    company_name: str | None = Field(default=None, max_length=200)
    contact_person: str | None = Field(default=None, max_length=150)
    email: str | None = Field(default=None, max_length=320)
    phone: str | None = Field(default=None, max_length=40)
    address_line1: str | None = Field(default=None, max_length=200)
    address_line2: str | None = Field(default=None, max_length=200)
    city: str | None = Field(default=None, max_length=100)
    state: str | None = Field(default=None, max_length=100)
    postal_code: str | None = Field(default=None, max_length=20)
    country: str | None = Field(default=None, max_length=100)
    tax_id: str | None = Field(default=None, max_length=100)
    tax_number: str | None = Field(default=None, max_length=100)
    opening_balance: Decimal = Field(default=Decimal("0.00"), ge=0, decimal_places=2)
    credit_limit: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    payment_terms: str | None = Field(default=None, max_length=100)
    notes: str | None = None

    @field_validator("vendor_code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("name", "vendor_name", "contact_person", "city", "state", "country", "tax_id", mode="before")
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        return value.strip() if isinstance(value, str) else value

    @model_validator(mode="after")
    def require_vendor_name(self) -> "VendorCreate":
        if not self.name and not self.vendor_name:
            raise ValueError("name or vendor_name is required")
        return self


class VendorUpdate(BaseModel):
    vendor_code: str | None = Field(default=None, min_length=1, max_length=50)
    name: str | None = Field(default=None, min_length=1, max_length=150)
    vendor_name: str | None = Field(default=None, max_length=150)
    address: str | None = Field(default=None, max_length=200)
    company_name: str | None = Field(default=None, max_length=200)
    contact_person: str | None = Field(default=None, max_length=150)
    email: str | None = Field(default=None, max_length=320)
    phone: str | None = Field(default=None, max_length=40)
    address_line1: str | None = Field(default=None, max_length=200)
    address_line2: str | None = Field(default=None, max_length=200)
    city: str | None = Field(default=None, max_length=100)
    state: str | None = Field(default=None, max_length=100)
    postal_code: str | None = Field(default=None, max_length=20)
    country: str | None = Field(default=None, max_length=100)
    tax_id: str | None = Field(default=None, max_length=100)
    tax_number: str | None = Field(default=None, max_length=100)
    opening_balance: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    credit_limit: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    payment_terms: str | None = Field(default=None, max_length=100)
    notes: str | None = None
    status: str | None = Field(default=None, pattern="^(active|inactive|suspended)$")
    is_active: bool | None = None

    @field_validator("vendor_code")
    @classmethod
    def normalize_code(cls, value: str | None) -> str | None:
        return value.strip().upper() if value is not None else None

    @field_validator("name", "vendor_name", "contact_person", "city", "state", "country", "tax_id", mode="before")
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        return value.strip() if isinstance(value, str) else value


class VendorRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    company_id: UUID
    branch_id: UUID | None
    vendor_code: str
    name: str
    vendor_name: str
    company_name: str | None
    contact_person: str | None
    email: str | None
    phone: str | None
    address_line1: str | None
    address_line2: str | None
    city: str | None
    state: str | None
    postal_code: str | None
    country: str | None
    tax_id: str | None
    tax_number: str | None
    opening_balance: Decimal
    credit_limit: Decimal | None
    payment_terms: str | None
    notes: str | None
    status: str
    is_active: bool
    deleted_at: datetime | None
    created_at: datetime
    updated_at: datetime


class VendorListResponse(BaseModel):
    items: list[VendorRead]
    total: int
    page: int
    page_size: int
    pages: int
