from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import has_permission
from app.db.models import (
    Permission,
    Role,
    UserBranch,
    UserCompany,
    UserPermissionOverride,
    UserRole,
)
from app.modules.roles.repository import RoleRepository
from app.modules.roles.schemas import (
    PermissionCreate,
    RoleCreate,
    RoleUpdate,
    UserPermissionOverrideCreate,
)


class RoleService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repository = RoleRepository(session)

    async def list_roles(self, user_id: UUID, company_id: UUID | None = None) -> list[Role]:
        if company_id is not None and not await self._company_access(user_id, company_id):
            raise HTTPException(status_code=403, detail="Organization scope is not allowed.")
        return await self.repository.list_roles(company_id)

    async def create_role(self, data: RoleCreate, user_id: UUID, is_dev_context: bool = False) -> Role:
        if data.is_system and data.company_id is not None:
            raise HTTPException(status_code=422, detail="System roles cannot be company-scoped.")
        if not data.is_system and data.company_id is None:
            raise HTTPException(status_code=422, detail="Company roles require company_id.")
        if not is_dev_context:
            await self._require_management(
                user_id, "roles.role.manage", None if data.is_system else data.company_id
            )
        if data.company_id is not None and not await self._company_access(user_id, data.company_id):
            raise HTTPException(status_code=403, detail="Organization scope is not allowed.")
        role = Role(**data.model_dump())
        self.session.add(role)
        await self.session.commit()
        await self.session.refresh(role)
        return role

    async def get_role(
        self, role_id: UUID, user_id: UUID | None = None, is_dev_context: bool = False
    ) -> Role:
        role = await self.repository.get_role(role_id)
        if role is None:
            raise HTTPException(status_code=404, detail="Role not found.")
        if role.is_system and user_id is not None and not is_dev_context and not await has_permission(
            self.session, user_id, "roles.role.manage"
        ):
            raise HTTPException(status_code=403, detail="Only global administrators can manage system roles.")
        if role.company_id is not None and user_id is not None and not await self._company_access(user_id, role.company_id):
            raise HTTPException(status_code=403, detail="Organization scope is not allowed.")
        return role

    async def update_role(
        self, role_id: UUID, data: RoleUpdate, user_id: UUID | None = None, is_dev_context: bool = False
    ) -> Role:
        role = await self.get_role(role_id, user_id, is_dev_context)
        if user_id is not None and not is_dev_context:
            await self._require_management(user_id, "roles.role.manage", role.company_id)
        if role.is_system and data.company_id is not None:
            raise HTTPException(status_code=422, detail="System roles cannot be company-scoped.")
        for key, value in data.model_dump(exclude_unset=True).items():
            setattr(role, key, value)
        if data.is_active is not None and data.status is None:
            role.status = "active" if data.is_active else "inactive"
        if data.status is not None and data.is_active is None:
            role.is_active = data.status == "active"
        await self.session.commit()
        await self.session.refresh(role)
        return role

    async def permissions(self) -> list[Permission]:
        return await self.repository.list_permissions()

    async def create_permission(
        self, data: PermissionCreate, actor_id: UUID | None = None, is_dev_context: bool = False
    ) -> Permission:
        if actor_id is not None and not is_dev_context:
            await self._require_management(actor_id, "roles.role.manage", None)
        if await self.session.scalar(select(Permission).where(Permission.code == data.code)):
            raise HTTPException(status_code=409, detail="Permission already exists.")
        permission = Permission(**data.model_dump())
        self.session.add(permission)
        await self.session.commit()
        await self.session.refresh(permission)
        return permission

    async def replace_permissions(
        self, role_id: UUID, permission_ids: list[UUID], user_id: UUID | None = None,
        is_dev_context: bool = False,
    ) -> Role:
        role = await self.get_role(role_id, user_id, is_dev_context)
        if user_id is not None and not is_dev_context:
            await self._require_management(user_id, "roles.role.manage", role.company_id)
        for permission_id in permission_ids:
            if await self.repository.get_permission(permission_id) is None:
                raise HTTPException(status_code=404, detail=f"Permission {permission_id} not found.")
        await self.repository.replace_permissions(role.id, permission_ids)
        await self.session.commit()
        return role

    async def assign_role(
        self, user_id: UUID, role_id: UUID, actor_id: UUID | None = None, is_dev_context: bool = False
    ) -> Role:
        role = await self.get_role(role_id, actor_id, is_dev_context)
        if actor_id is not None and not is_dev_context:
            await self._require_management(
                actor_id, "roles.assignment.manage", role.company_id
            )
        if role.company_id is not None and not await self._company_access(user_id, role.company_id):
            raise HTTPException(status_code=403, detail="User is not assigned to the role company.")
        existing = await self.session.scalar(
            select(UserRole).where(UserRole.user_id == user_id, UserRole.role_id == role_id)
        )
        if existing is None:
            await self.repository.assign_role(user_id, role_id)
            await self.session.commit()
        return role

    async def remove_role(
        self,
        user_id: UUID,
        role_id: UUID,
        actor_id: UUID | None = None,
        is_dev_context: bool = False,
    ) -> None:
        role = await self.get_role(role_id, actor_id, is_dev_context)
        if actor_id is not None and not is_dev_context:
            await self._require_management(
                actor_id, "roles.assignment.manage", role.company_id
            )
        if role.company_id is not None and not await self._company_access(user_id, role.company_id):
            raise HTTPException(status_code=403, detail="User is not assigned to the role company.")
        await self.repository.remove_role(user_id, role_id)
        await self.session.commit()

    async def user_roles(self, user_id: UUID, actor_id: UUID | None = None) -> list[Role]:
        roles = await self.repository.user_roles(user_id)
        if actor_id is None:
            return roles
        visible: list[Role] = []
        for role in roles:
            if role.is_system or await self._company_access(actor_id, role.company_id):
                visible.append(role)
        return visible

    async def create_override(
        self,
        user_id: UUID,
        data: UserPermissionOverrideCreate,
        actor_id: UUID | None = None,
        is_dev_context: bool = False,
    ) -> UserPermissionOverride:
        if await self.repository.get_permission(data.permission_id) is None:
            raise HTTPException(status_code=404, detail="Permission not found.")
        if data.branch_id is not None and data.company_id is None:
            raise HTTPException(status_code=422, detail="Branch overrides require company_id.")
        if actor_id is not None and not is_dev_context:
            await self._require_management(actor_id, "roles.override.manage", data.company_id)
        if data.branch_id is not None:
            branch_access = await self.session.scalar(
                select(UserBranch.branch_id).where(
                    UserBranch.user_id == user_id,
                    UserBranch.branch_id == data.branch_id,
                    UserBranch.company_id == data.company_id,
                )
            )
            if branch_access is None:
                raise HTTPException(status_code=403, detail="User is not assigned to the override branch.")
        elif data.company_id is not None and not await self._company_access(user_id, data.company_id):
            raise HTTPException(status_code=403, detail="User is not assigned to the override company.")
        override = UserPermissionOverride(user_id=user_id, **data.model_dump())
        self.session.add(override)
        await self.session.commit()
        await self.session.refresh(override)
        return override

    async def list_overrides(self, user_id: UUID, actor_id: UUID | None = None) -> list[UserPermissionOverride]:
        overrides = await self.repository.overrides(user_id)
        if actor_id is None:
            return overrides
        visible: list[UserPermissionOverride] = []
        for override in overrides:
            if override.company_id is None or await self._company_access(actor_id, override.company_id):
                visible.append(override)
        return visible

    async def deactivate_override(
        self, override_id: UUID, actor_id: UUID | None = None, is_dev_context: bool = False
    ) -> None:
        override = await self.session.get(UserPermissionOverride, override_id)
        if override is None:
            raise HTTPException(status_code=404, detail="Permission override not found.")
        if actor_id is not None and not is_dev_context:
            await self._require_management(actor_id, "roles.override.manage", override.company_id)
        override.is_active = False
        await self.session.commit()

    async def _company_access(self, user_id: UUID, company_id: UUID) -> bool:
        return (
            await self.session.scalar(
                select(UserCompany.company_id).where(
                    UserCompany.user_id == user_id, UserCompany.company_id == company_id
                )
            )
        ) is not None

    async def _require_management(
        self, actor_id: UUID, permission: str, company_id: UUID | None
    ) -> None:
        if not await has_permission(self.session, actor_id, permission, company_id):
            raise HTTPException(status_code=403, detail="Role management permission is not allowed.")
