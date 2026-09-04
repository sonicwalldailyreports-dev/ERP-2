from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import RequestContext, require_permission
from app.core.dependencies import get_db_session
from app.modules.users.schemas import (
    AuditActivityRead,
    LoginHistoryRead,
    PasswordResetAdminRequest,
    PermissionSummary,
    UserAssignmentsUpdate,
    UserCreate,
    UserListResponse,
    UserRead,
    UserUpdate,
)
from app.modules.users.service import UserService

router = APIRouter(prefix="/users", tags=["users"])
Session = Annotated[AsyncSession, Depends(get_db_session)]
ReadContext = Annotated[RequestContext, Depends(require_permission("users.user.view", allow_any_company=True))]
CreateContext = Annotated[RequestContext, Depends(require_permission("users.user.create", company_param="company_id"))]
ManageContext = Annotated[RequestContext, Depends(require_permission("users.user.edit", allow_any_company=True))]
ActivateContext = Annotated[RequestContext, Depends(require_permission("users.user.activate", allow_any_company=True))]
ResetContext = Annotated[RequestContext, Depends(require_permission("users.user.reset_password", allow_any_company=True))]
LoginHistoryContext = Annotated[RequestContext, Depends(require_permission("users.user.login_history", allow_any_company=True))]
AuditContext = Annotated[RequestContext, Depends(require_permission("users.user.audit", allow_any_company=True))]


@router.get("", response_model=UserListResponse)
async def list_users(
    session: Session, context: ReadContext, company_id: UUID | None = None, branch_id: UUID | None = None,
    search: str | None = None, status_filter: str | None = Query(default=None, alias="status"),
    page: int = 1, page_size: int = 25,
):
    page = max(1, min(page, 10000))
    page_size = max(1, min(page_size, 100))
    return await UserService(session).list(
        context.user_id, company_id, branch_id, search, status_filter, page, page_size, context.is_dev_context
    )


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def create_user(data: UserCreate, session: Session, context: CreateContext, company_id: UUID | None = None):
    return await UserService(session).create(data, context.user_id, company_id, context.is_dev_context)


@router.get("/{user_id}", response_model=UserRead)
async def get_user(user_id: UUID, session: Session, context: ReadContext):
    service = UserService(session)
    user = await service._target(user_id, context.user_id, context.is_dev_context)
    return await service._view(user)


@router.patch("/{user_id}", response_model=UserRead)
async def update_user(user_id: UUID, data: UserUpdate, session: Session, context: ManageContext, company_id: UUID | None = None):
    return await UserService(session).update(user_id, data, context.user_id, company_id, context.is_dev_context)


@router.put("/{user_id}/assignments", response_model=UserRead)
async def update_assignments(
    user_id: UUID, data: UserAssignmentsUpdate, session: Session, context: ManageContext,
    company_id: UUID | None = None,
):
    return await UserService(session).update(
        user_id, UserUpdate(
            company_ids=data.company_ids, branch_assignments=data.branch_assignments, role_ids=data.role_ids
        ), context.user_id, company_id, context.is_dev_context
    )


@router.post("/{user_id}/activate", response_model=UserRead)
async def activate_user(user_id: UUID, session: Session, context: ActivateContext):
    return await UserService(session).set_active(user_id, True, context.user_id, context.is_dev_context)


@router.post("/{user_id}/deactivate", response_model=UserRead)
async def deactivate_user(user_id: UUID, session: Session, context: ActivateContext):
    return await UserService(session).set_active(user_id, False, context.user_id, context.is_dev_context)


@router.post("/{user_id}/reset-password")
async def reset_password(user_id: UUID, data: PasswordResetAdminRequest, session: Session, context: ResetContext):
    generated = await UserService(session).reset_password(user_id, data.new_password, context.user_id, context.is_dev_context)
    return {"message": "Password reset successfully.", **({"temporary_password": generated} if generated else {})}


@router.get("/{user_id}/permissions-summary", response_model=PermissionSummary)
async def permission_summary(user_id: UUID, session: Session, context: ReadContext):
    return await UserService(session).permission_summary(user_id, context.user_id, context.is_dev_context)


@router.get("/{user_id}/permissions", response_model=PermissionSummary, include_in_schema=False)
async def permission_summary_alias(user_id: UUID, session: Session, context: ReadContext):
    return await UserService(session).permission_summary(user_id, context.user_id, context.is_dev_context)


@router.get("/{user_id}/login-history", response_model=list[LoginHistoryRead])
async def login_history(user_id: UUID, session: Session, context: LoginHistoryContext, limit: int = 100):
    return await UserService(session).login_history(user_id, context.user_id, context.is_dev_context, max(1, min(limit, 500)))


@router.get("/{user_id}/audit-activity", response_model=list[AuditActivityRead])
async def audit_activity(user_id: UUID, session: Session, context: AuditContext, limit: int = 100):
    return await UserService(session).audit_activity(user_id, context.user_id, context.is_dev_context, max(1, min(limit, 500)))
