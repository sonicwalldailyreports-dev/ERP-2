from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import RequestContext, require_permission
from app.core.dependencies import get_db_session
from app.db.models import Permission, RolePermission
from app.modules.roles.schemas import (
    PermissionCreate,
    PermissionRead,
    RoleAssignment,
    RoleCreate,
    RolePermissionsUpdate,
    RoleRead,
    RoleUpdate,
    UserPermissionOverrideCreate,
    UserPermissionOverrideRead,
)
from app.modules.roles.service import RoleService

router = APIRouter(prefix="/roles", tags=["roles"])
Session = Annotated[AsyncSession, Depends(get_db_session)]
Read = Annotated[RequestContext, Depends(require_permission("roles.role.read", allow_any_company=True))]
Manage = Annotated[RequestContext, Depends(require_permission("roles.role.manage", allow_any_company=True))]
PermissionReadContext = Annotated[RequestContext, Depends(require_permission("roles.permission.view", allow_any_company=True))]
AssignmentContext = Annotated[RequestContext, Depends(require_permission("roles.assignment.manage", allow_any_company=True))]
OverrideContext = Annotated[RequestContext, Depends(require_permission("roles.override.manage", allow_any_company=True))]


@router.get("", response_model=list[RoleRead])
async def list_roles(session: Session, context: Read, company_id: UUID | None = None):
    return await RoleService(session).list_roles(context.user_id, company_id)


@router.post("", response_model=RoleRead, status_code=status.HTTP_201_CREATED)
async def create_role(data: RoleCreate, session: Session, context: Manage):
    return await RoleService(session).create_role(data, context.user_id, context.is_dev_context)


@router.get("/permissions", response_model=list[PermissionRead])
async def list_permissions(session: Session, _: PermissionReadContext):
    return await RoleService(session).permissions()


@router.post("/permissions", response_model=PermissionRead, status_code=status.HTTP_201_CREATED)
async def create_permission(data: PermissionCreate, session: Session, context: Manage):
    return await RoleService(session).create_permission(
        data, context.user_id, context.is_dev_context
    )


@router.get("/{role_id}", response_model=RoleRead)
async def get_role(role_id: UUID, session: Session, _: Read):
    return await RoleService(session).get_role(role_id, _.user_id, _.is_dev_context)


@router.patch("/{role_id}", response_model=RoleRead)
async def update_role(role_id: UUID, data: RoleUpdate, session: Session, _: Manage):
    return await RoleService(session).update_role(role_id, data, _.user_id, _.is_dev_context)


@router.put("/{role_id}/permissions", response_model=RoleRead)
async def replace_role_permissions(
    role_id: UUID, data: RolePermissionsUpdate, session: Session, _: Manage
):
    return await RoleService(session).replace_permissions(
        role_id, data.permission_ids, _.user_id, _.is_dev_context
    )


@router.get("/{role_id}/permissions", response_model=list[PermissionRead])
async def role_permissions(role_id: UUID, session: Session, _: Read):
    role = await RoleService(session).get_role(role_id, _.user_id, _.is_dev_context)
    result = await session.scalars(
        select(Permission)
        .join(RolePermission, RolePermission.permission_id == Permission.id)
        .where(RolePermission.role_id == role.id)
    )
    return list(result)


@router.post("/users/{user_id}", response_model=RoleRead)
async def assign_role(user_id: UUID, data: RoleAssignment, session: Session, _: AssignmentContext):
    return await RoleService(session).assign_role(
        user_id, data.role_id, _.user_id, _.is_dev_context
    )


@router.delete("/users/{user_id}/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_role(user_id: UUID, role_id: UUID, session: Session, _: AssignmentContext):
    await RoleService(session).remove_role(user_id, role_id, _.user_id, _.is_dev_context)


@router.get("/users/{user_id}", response_model=list[RoleRead])
async def user_roles(user_id: UUID, session: Session, _: Read):
    return await RoleService(session).user_roles(user_id, _.user_id)


@router.post("/users/{user_id}/overrides", response_model=UserPermissionOverrideRead)
async def create_override(
    user_id: UUID, data: UserPermissionOverrideCreate, session: Session, _: OverrideContext
):
    return await RoleService(session).create_override(user_id, data, _.user_id, _.is_dev_context)


@router.get("/users/{user_id}/overrides", response_model=list[UserPermissionOverrideRead])
async def list_overrides(user_id: UUID, session: Session, _: Read):
    return await RoleService(session).list_overrides(user_id, _.user_id)


@router.delete("/overrides/{override_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_override(override_id: UUID, session: Session, _: OverrideContext):
    await RoleService(session).deactivate_override(override_id, _.user_id, _.is_dev_context)
