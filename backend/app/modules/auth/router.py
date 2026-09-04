from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import effective_permissions
from app.core.config import Settings
from app.core.dependencies import get_current_settings, get_db_session
from app.db.models import User
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.schemas import (
    ChangePasswordRequest,
    LoginRequest,
    PasswordResetConfirm,
    PasswordResetRequest,
    RefreshRequest,
    TokenResponse,
    UserRead,
)
from app.modules.auth.service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])
Session = Annotated[AsyncSession, Depends(get_db_session)]
SettingsDependency = Annotated[Settings, Depends(get_current_settings)]


def _client_data(request: Request) -> tuple[str | None, str | None]:
    return request.headers.get("user-agent"), request.client.host if request.client else None


@router.post("/login", response_model=TokenResponse)
async def login(data: LoginRequest, request: Request, session: Session, settings: SettingsDependency):
    user_agent, ip = _client_data(request)
    return await AuthService(session, settings).login(data, user_agent, ip)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(data: RefreshRequest, request: Request, session: Session, settings: SettingsDependency):
    user_agent, ip = _client_data(request)
    return await AuthService(session, settings).refresh(data.refresh_token, user_agent, ip)


@router.post("/password-reset/request", status_code=202)
async def request_password_reset(data: PasswordResetRequest, session: Session, settings: SettingsDependency):
    # The returned token is intentionally kept internal for a future notification provider.
    await AuthService(session, settings).request_password_reset(data.email)
    return {"message": "If the account exists, reset instructions will be sent."}


@router.post("/password-reset/confirm", status_code=204)
async def confirm_password_reset(data: PasswordResetConfirm, session: Session, settings: SettingsDependency):
    await AuthService(session, settings).confirm_password_reset(data)
    return Response(status_code=204)


@router.post("/logout", status_code=204)
async def logout(data: RefreshRequest, session: Session, settings: SettingsDependency):
    await AuthService(session, settings).logout(data.refresh_token)
    return Response(status_code=204)


@router.post("/change-password", status_code=204)
async def change_password(data: ChangePasswordRequest, user: Annotated[User, Depends(get_current_user)], session: Session, settings: SettingsDependency):
    await AuthService(session, settings).change_password(user, data)
    return Response(status_code=204)


@router.get("/me", response_model=UserRead)
async def me(user: Annotated[User, Depends(get_current_user)]):
    return user


@router.get("/me/permissions", response_model=list[str])
async def my_permissions(
    user: Annotated[User, Depends(get_current_user)],
    session: Session,
    company_id: UUID | None = None,
    branch_id: UUID | None = None,
):
    if branch_id is not None and company_id is None:
        raise HTTPException(status_code=422, detail="branch_id requires company_id.")
    return sorted(await effective_permissions(session, user.id, company_id, branch_id))
