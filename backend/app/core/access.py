"""Request context and database-backed permission evaluation."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

import jwt
from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import bind_audit_actor
from app.core.config import Settings
from app.core.dependencies import get_current_settings, get_db_session
from app.db.models import (
    Permission,
    Role,
    RolePermission,
    User,
    UserBranch,
    UserCompany,
    UserPermissionOverride,
    UserRole,
)
from app.modules.auth.dependencies import bearer
from app.modules.auth.repository import AuthRepository
from app.modules.auth.security import decode_access_token


@dataclass(frozen=True)
class RequestContext:
    user_id: UUID
    company_id: UUID | None = None
    branch_id: UUID | None = None
    is_dev_context: bool = False


def _parse_uuid(value: str | UUID | None) -> UUID | None:
    if value is None:
        return None
    try:
        return value if isinstance(value, UUID) else UUID(str(value))
    except (TypeError, ValueError):
        return None


async def get_request_context(
    request: Request,
    settings: Annotated[Settings, Depends(get_current_settings)],
    x_dev_user_id: Annotated[UUID | None, Header(alias="X-Dev-User-ID")] = None,
) -> RequestContext:
    """Legacy development context used only by explicitly enabled local apps."""
    is_loopback = request.client is not None and request.client.host in {"127.0.0.1", "::1"}
    if (
        x_dev_user_id is None
        or not settings.dev_user_header_enabled
        or not is_loopback
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
        )
    return RequestContext(user_id=x_dev_user_id, is_dev_context=True)


async def _authenticated_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None,
    session: AsyncSession,
    settings: Settings,
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


async def has_permission(
    session: AsyncSession,
    user_id: UUID,
    permission_code: str,
    company_id: UUID | None = None,
    branch_id: UUID | None = None,
) -> bool:
    candidates = [permission_code]
    if permission_code.endswith(".view"):
        candidates.append(f"{permission_code[:-5]}.read")
    if permission_code.endswith(".edit"):
        candidates.append(f"{permission_code[:-5]}.update")
    if permission_code.startswith("cashbook.account."):
        candidates.append(permission_code.replace("cashbook.account.", "cashbook.cash_account.", 1))
    elif permission_code.startswith("cashbook.cash_account."):
        candidates.append(permission_code.replace("cashbook.cash_account.", "cashbook.account.", 1))
    for candidate in candidates:
        if await _has_permission_exact(session, user_id, candidate, company_id, branch_id):
            return True
    return False


async def _has_permission_exact(
    session: AsyncSession,
    user_id: UUID,
    permission_code: str,
    company_id: UUID | None,
    branch_id: UUID | None,
) -> bool:
    """Evaluate overrides first, then active role grants.

    A more specific override wins. Any matching deny wins over grants at the
    same scope, which makes emergency revocation predictable.
    """
    if branch_id is not None and company_id is None:
        return False
    if company_id is not None and not await _has_scope(session, user_id, company_id, branch_id):
        return False
    permission = await session.scalar(
        select(Permission).where(Permission.code == permission_code, Permission.is_active.is_(True))
    )
    if permission is None:
        return False

    overrides = list(
        await session.scalars(
            select(UserPermissionOverride).where(
                UserPermissionOverride.user_id == user_id,
                UserPermissionOverride.permission_id == permission.id,
                UserPermissionOverride.is_active.is_(True),
            )
        )
    )
    candidates: list[tuple[int, bool]] = []
    for override in overrides:
        if override.company_id is not None and override.company_id != company_id:
            continue
        if override.branch_id is not None and override.branch_id != branch_id:
            continue
        specificity = (2 if override.company_id is not None else 0) + (1 if override.branch_id is not None else 0)
        candidates.append((specificity, override.is_granted))
    if candidates:
        best = max(item[0] for item in candidates)
        best_values = [granted for specificity, granted in candidates if specificity == best]
        return all(best_values)

    role_grant = await session.scalar(
        select(Permission.id)
        .join(RolePermission, RolePermission.permission_id == Permission.id)
        .join(Role, Role.id == RolePermission.role_id)
        .join(UserRole, UserRole.role_id == Role.id)
        .where(
            UserRole.user_id == user_id,
            Permission.id == permission.id,
            Role.is_active.is_(True),
            Role.status == "active",
            (Role.is_system.is_(True) | (Role.company_id == company_id)),
        )
    )
    return role_grant is not None


async def effective_permissions(
    session: AsyncSession,
    user_id: UUID,
    company_id: UUID | None = None,
    branch_id: UUID | None = None,
) -> set[str]:
    if branch_id is not None and company_id is None:
        return set()
    if company_id is not None and not await _has_scope(session, user_id, company_id, branch_id):
        return set()
    permissions = list(await session.scalars(select(Permission).where(Permission.is_active.is_(True))))
    result: set[str] = set()
    for permission in permissions:
        if await has_permission(session, user_id, permission.code, company_id, branch_id):
            result.add(permission.code)
    return result


async def has_permission_in_any_company(
    session: AsyncSession, user_id: UUID, permission_code: str
) -> bool:
    """Return whether a user has a permission in at least one assigned company."""
    if await has_permission(session, user_id, permission_code):
        return True
    company_ids = list(
        await session.scalars(select(UserCompany.company_id).where(UserCompany.user_id == user_id))
    )
    for company_id in company_ids:
        if await has_permission(session, user_id, permission_code, company_id):
            return True
    return False


async def _has_scope(
    session: AsyncSession, user_id: UUID, company_id: UUID | None, branch_id: UUID | None
) -> bool:
    if company_id is None:
        return True
    company_access = await session.scalar(
        select(UserCompany.company_id).where(
            UserCompany.user_id == user_id, UserCompany.company_id == company_id
        )
    )
    if company_access is None:
        return False
    if branch_id is None:
        return True
    return (
        await session.scalar(
            select(UserBranch.branch_id).where(
                UserBranch.user_id == user_id,
                UserBranch.company_id == company_id,
                UserBranch.branch_id == branch_id,
            )
        )
    ) is not None


def require_permission(
    permission_code: str,
    *,
    company_param: str = "company_id",
    branch_param: str = "branch_id",
    allow_any_company: bool = False,
) -> Callable:
    """FastAPI dependency enforcing permission and tenant/branch scope.

    ``X-Dev-User-ID`` is disabled by default and only works when explicitly
    enabled for local development/test traffic.
    """
    async def dependency(
        request: Request,
        credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
        session: Annotated[AsyncSession, Depends(get_db_session)],
        settings: Annotated[Settings, Depends(get_current_settings)],
    ) -> RequestContext:
        dev_id = _parse_uuid(request.headers.get("X-Dev-User-ID"))
        is_loopback = request.client is not None and request.client.host in {"127.0.0.1", "::1"}
        if (
            dev_id is not None
            and settings.dev_user_header_enabled
            and is_loopback
        ):
            user = await AuthRepository(session).get_user(dev_id)
            if user is None or not user.is_active:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")
            bind_audit_actor(dev_id)
            return RequestContext(user_id=dev_id, is_dev_context=True)

        user = await _authenticated_user(request, credentials, session, settings)
        company_id = _parse_uuid(
            request.path_params.get(company_param) or request.query_params.get(company_param)
        )
        branch_id = _parse_uuid(
            request.path_params.get(branch_param) or request.query_params.get(branch_param)
        )
        if not await _has_scope(session, user.id, company_id, branch_id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization scope is not allowed.")
        permitted = await has_permission(session, user.id, permission_code, company_id, branch_id)
        if company_id is None and allow_any_company:
            permitted = await has_permission_in_any_company(session, user.id, permission_code)
        if not permitted:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied.")
        return RequestContext(user.id, company_id, branch_id)

    return dependency
