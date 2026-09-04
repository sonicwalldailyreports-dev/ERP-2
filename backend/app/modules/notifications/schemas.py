from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class NotificationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    company_id: UUID | None
    branch_id: UUID | None
    event_type: str
    title: str
    message: str
    payload: dict | None
    read_at: datetime | None
    created_at: datetime


class NotificationListResponse(BaseModel):
    items: list[NotificationRead]
    unread_count: int = Field(ge=0)


class NotificationPreferences(BaseModel):
    email_enabled: bool = False
