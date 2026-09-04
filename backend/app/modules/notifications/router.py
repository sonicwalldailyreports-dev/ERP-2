from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import RequestContext, require_permission
from app.core.dependencies import get_db_session
from app.modules.notifications.schemas import NotificationListResponse, NotificationRead
from app.modules.notifications.service import NotificationService

router = APIRouter(prefix="/notifications", tags=["notifications"])
Session = Annotated[AsyncSession, Depends(get_db_session)]
Context = Annotated[
    RequestContext, Depends(require_permission("notifications.notification.view", allow_any_company=True))
]


@router.get("", response_model=NotificationListResponse)
async def list_notifications(
    session: Session,
    context: Context,
    unread_only: bool = Query(False),
    limit: int = Query(50, ge=1, le=200),
):
    items, unread_count = await NotificationService(session).list(
        context.user_id, unread_only=unread_only, limit=limit
    )
    return NotificationListResponse(items=items, unread_count=unread_count)


@router.post("/read-all", status_code=status.HTTP_204_NO_CONTENT)
async def mark_all_notifications_read(session: Session, context: Context):
    await NotificationService(session).mark_all_read(context.user_id)


@router.post("/{notification_id}/read", response_model=NotificationRead)
async def mark_notification_read(notification_id: UUID, session: Session, context: Context):
    try:
        return await NotificationService(session).mark_read(notification_id, context.user_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
