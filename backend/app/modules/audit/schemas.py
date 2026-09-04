from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AuditLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID | None
    company_id: UUID | None
    branch_id: UUID | None
    action: str
    module: str
    entity_type: str
    entity_id: UUID | None
    timestamp: datetime
    ip_address: str | None
    user_agent: str | None
    request_id: str | None
    before_data: dict[str, Any] | None
    after_data: dict[str, Any] | None
    details: str | None


class AuditLogFilters(BaseModel):
    date_from: datetime | None = None
    date_to: datetime | None = None
    user_id: UUID | None = None
    module: str | None = Field(default=None, max_length=80)
    action: str | None = Field(default=None, max_length=50)
    entity: str | None = Field(default=None, max_length=100)
    entity_id: UUID | None = None
    company_id: UUID | None = None
    branch_id: UUID | None = None
    page: int = Field(default=1, ge=1, le=10000)
    page_size: int = Field(default=25, ge=1, le=100)


class AuditLogListResponse(BaseModel):
    items: list[AuditLogRead]
    total: int
    page: int
    page_size: int
    pages: int
