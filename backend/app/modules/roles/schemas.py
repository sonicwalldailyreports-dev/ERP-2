from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


def validate_permission_code(value: str) -> str:
    parts = value.split(".")
    if len(parts) != 3 or any(not part or not part.replace("_", "").isalnum() for part in parts):
        raise ValueError("Permission must use module.resource.action format.")
    return value.lower()


class PermissionCreate(BaseModel):
    code: str
    description: str | None = None

    _code = field_validator("code")(validate_permission_code)


class PermissionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    code: str
    description: str | None
    is_active: bool


class RoleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = None
    company_id: UUID | None = None
    is_system: bool = False


class RoleUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = None
    is_active: bool | None = None
    status: str | None = Field(default=None, pattern="^(active|inactive)$")


class RoleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    company_id: UUID | None
    name: str
    description: str | None
    is_system: bool
    is_active: bool
    status: str
    created_at: datetime
    updated_at: datetime


class RolePermissionsUpdate(BaseModel):
    permission_ids: list[UUID]


class RoleAssignment(BaseModel):
    role_id: UUID


class UserPermissionOverrideCreate(BaseModel):
    permission_id: UUID
    company_id: UUID | None = None
    branch_id: UUID | None = None
    is_granted: bool


class UserPermissionOverrideRead(UserPermissionOverrideCreate):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    user_id: UUID
    is_active: bool
