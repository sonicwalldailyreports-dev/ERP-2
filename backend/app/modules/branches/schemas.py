from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class BranchCreate(BaseModel):
    company_id: UUID
    name: str = Field(min_length=1, max_length=150)
    code: str = Field(min_length=1, max_length=50)


class BranchUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    code: str | None = Field(default=None, min_length=1, max_length=50)


class BranchRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    company_id: UUID
    name: str
    code: str
    is_active: bool
    deleted_at: datetime | None
