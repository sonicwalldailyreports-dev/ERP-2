from typing import Annotated
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import bind_audit_actor
from app.core.config import Settings
from app.core.dependencies import get_current_settings, get_db_session
from app.db.models import User
from app.modules.auth.repository import AuthRepository
from app.modules.auth.security import decode_access_token

bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_current_settings)],
) -> User:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")
    try:
        user_id = UUID(decode_access_token(credentials.credentials, settings))
    except (ValueError, TypeError, jwt.PyJWTError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid access token.") from None
    user = await AuthRepository(session).get_user(user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")
    request.state.user_id = user.id
    bind_audit_actor(user.id)
    return user
