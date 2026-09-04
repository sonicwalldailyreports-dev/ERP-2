from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Permission, Role, RolePermission, UserPermissionOverride, UserRole


class RoleRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_roles(self, company_id: UUID | None = None) -> list[Role]:
        query = select(Role)
        if company_id is not None:
            query = query.where((Role.company_id == company_id) | Role.is_system.is_(True))
        else:
            query = query.where(Role.is_system.is_(True))
        return list(await self.session.scalars(query.order_by(Role.name)))

    async def get_role(self, role_id: UUID) -> Role | None:
        return await self.session.scalar(select(Role).where(Role.id == role_id))

    async def list_permissions(self) -> list[Permission]:
        return list(await self.session.scalars(select(Permission).where(Permission.is_active.is_(True)).order_by(Permission.code)))

    async def get_permission(self, permission_id: UUID) -> Permission | None:
        return await self.session.scalar(select(Permission).where(Permission.id == permission_id))

    async def replace_permissions(self, role_id: UUID, permission_ids: list[UUID]) -> None:
        await self.session.execute(delete(RolePermission).where(RolePermission.role_id == role_id))
        for permission_id in set(permission_ids):
            self.session.add(RolePermission(role_id=role_id, permission_id=permission_id))

    async def assign_role(self, user_id: UUID, role_id: UUID) -> UserRole:
        assignment = UserRole(user_id=user_id, role_id=role_id)
        self.session.add(assignment)
        return assignment

    async def remove_role(self, user_id: UUID, role_id: UUID) -> None:
        await self.session.execute(
            delete(UserRole).where(UserRole.user_id == user_id, UserRole.role_id == role_id)
        )

    async def user_roles(self, user_id: UUID) -> list[Role]:
        return list(
            await self.session.scalars(
                select(Role)
                .join(UserRole, UserRole.role_id == Role.id)
                .where(UserRole.user_id == user_id)
                .order_by(Role.name)
            )
        )

    async def overrides(self, user_id: UUID) -> list[UserPermissionOverride]:
        return list(
            await self.session.scalars(
                select(UserPermissionOverride).where(
                    UserPermissionOverride.user_id == user_id,
                    UserPermissionOverride.is_active.is_(True),
                )
            )
        )
