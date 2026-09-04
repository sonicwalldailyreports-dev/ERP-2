from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class UserCreate(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    email: str = Field(min_length=3, max_length=320)
    full_name: str = Field(min_length=1, max_length=150)
    phone: str | None = Field(default=None, max_length=40)
    password: str = Field(min_length=12, max_length=512)
    company_ids: list[UUID] = Field(default_factory=list)
    branch_assignments: list["BranchAssignment"] = Field(default_factory=list)
    role_ids: list[UUID] = Field(default_factory=list)

    @field_validator("username", "email")
    @classmethod
    def normalize(cls, value: str) -> str:
        return value.strip().lower()


class UserUpdate(BaseModel):
    username: str | None = Field(default=None, min_length=1, max_length=100)
    email: str | None = Field(default=None, min_length=3, max_length=320)
    full_name: str | None = Field(default=None, min_length=1, max_length=150)
    phone: str | None = Field(default=None, max_length=40)
    status: str | None = Field(default=None, pattern="^(active|inactive|suspended)$")
    is_active: bool | None = None
    company_ids: list[UUID] | None = None
    branch_assignments: list["BranchAssignment"] | None = None
    role_ids: list[UUID] | None = None


class BranchAssignment(BaseModel):
    company_id: UUID
    branch_id: UUID


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    username: str | None
    email: str
    phone: str | None
    full_name: str
    status: str
    is_active: bool
    password_status: str
    last_login_at: datetime | None
    company_ids: list[UUID] = Field(default_factory=list)
    branch_assignments: list[BranchAssignment] = Field(default_factory=list)
    role_ids: list[UUID] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class UserListResponse(BaseModel):
    items: list[UserRead]
    total: int
    page: int
    page_size: int
    pages: int


class PasswordResetAdminRequest(BaseModel):
    new_password: str | None = Field(default=None, min_length=12, max_length=512)


class PermissionSummary(BaseModel):
    permissions: list[str]
    by_company: dict[str, list[str]] = Field(default_factory=dict)


class LoginHistoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    successful: bool
    failure_reason: str | None
    ip_address: str | None
    user_agent: str | None
    created_at: datetime


class AuditActivityRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID | None
    action: str
    entity_type: str
    entity_id: UUID | None
    details: str | None
    created_at: datetime


class UserAssignmentsUpdate(BaseModel):
    company_ids: list[UUID] = Field(default_factory=list)
    branch_assignments: list[BranchAssignment] = Field(default_factory=list)
    role_ids: list[UUID] = Field(default_factory=list)
