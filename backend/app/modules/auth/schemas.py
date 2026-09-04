from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=320)
    password: str = Field(min_length=1, max_length=512)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=32, max_length=512)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=512)
    new_password: str = Field(min_length=12, max_length=512)


class PasswordResetRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)


class PasswordResetConfirm(BaseModel):
    token: str = Field(min_length=32, max_length=512)
    new_password: str = Field(min_length=12, max_length=512)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    username: str | None = None
    email: str
    phone: str | None = None
    full_name: str
    is_active: bool
    status: str = "active"
    password_status: str = "set"
    last_login_at: datetime | None
