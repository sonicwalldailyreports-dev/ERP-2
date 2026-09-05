from __future__ import annotations

import json
import secrets
from math import ceil
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import effective_permissions, has_permission
from app.db.models import AuditLog, AuthSession, Role, User, UserBranch, UserCompany, UserRole
from app.modules.auth.security import hash_password
from app.modules.notifications.events import PASSWORD_RESET, USER_CREATED, DomainEvent
from app.modules.notifications.service import NotificationService
from app.modules.users.repository import UserRepository
from app.modules.users.schemas import (
    AuditActivityRead,
    BranchAssignment,
    LoginHistoryRead,
    PermissionSummary,
    UserAssignmentsUpdate,
    UserCreate,
    UserRead,
    UserUpdate,
)


class UserService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repository = UserRepository(session)

    async def _global_access(self, actor_id: UUID, dev: bool) -> bool:
        if dev:
            return True
        return await has_permission(self.session, actor_id, "users.user.edit")

    async def _target(self, user_id: UUID, actor_id: UUID, dev: bool) -> User:
        target = await self.repository.get(user_id)
        if target is None:
            raise HTTPException(404, "User not found.")
        if not await self._global_access(actor_id, dev):
            actor_companies = set(await self.repository.companies(actor_id))
            target_companies = set(await self.repository.companies(user_id))
            if not actor_companies.intersection(target_companies):
                raise HTTPException(403, "Organization scope is not allowed.")
        return target

    async def _validate_assignments(
        self, actor_id: UUID, company_ids: list[UUID], branches: list[BranchAssignment],
        role_ids: list[UUID], context_company: UUID | None, dev: bool,
    ) -> None:
        if len(company_ids) != len(set(company_ids)):
            raise HTTPException(422, "Duplicate company assignments are not allowed.")
        if context_company is not None and not dev and context_company not in company_ids:
            raise HTTPException(403, "Assignments must remain within the selected company.")
        global_access = await self._global_access(actor_id, dev)
        for company_id in company_ids:
            if await self.repository.valid_company(company_id) is None:
                raise HTTPException(404, f"Company {company_id} not found.")
            if not global_access and not await has_permission(
                self.session, actor_id, "users.user.manage", company_id
            ):
                raise HTTPException(403, "Organization scope is not allowed.")
        for assignment in branches:
            if assignment.company_id not in company_ids:
                raise HTTPException(422, "Every branch assignment requires its company assignment.")
            if await self.repository.valid_branch(assignment.company_id, assignment.branch_id) is None:
                raise HTTPException(404, f"Branch {assignment.branch_id} not found.")
        for role_id in role_ids:
            role = await self.repository.valid_role(role_id)
            if role is None:
                raise HTTPException(404, f"Role {role_id} not found.")
            if role.is_system and not global_access:
                raise HTTPException(403, "Only a global administrator can assign system roles.")
            if role.company_id is not None and role.company_id not in company_ids:
                raise HTTPException(422, "A user must be assigned to a role's company.")
            if role.company_id is not None and not global_access and not await has_permission(
                self.session, actor_id, "users.user.manage", role.company_id
            ):
                raise HTTPException(403, "Organization scope is not allowed.")

    async def _view(self, user: User) -> UserRead:
        return UserRead(
            **{key: getattr(user, key) for key in (
                "id", "username", "email", "phone", "full_name", "status", "is_active",
                "password_status", "last_login_at", "created_at", "updated_at"
            )},
            company_ids=await self.repository.companies(user.id),
            branch_assignments=[
                BranchAssignment(company_id=company_id, branch_id=branch_id)
                for company_id, branch_id in await self.repository.branches(user.id)
            ],
            role_ids=await self.repository.roles(user.id),
        )

    async def _audit(self, actor_id: UUID, target_id: UUID, action: str, details: dict) -> None:
        self.session.add(AuditLog(
            user_id=actor_id, action=action, entity_type="user", entity_id=target_id,
            details=json.dumps(details, default=str),
        ))

    async def _replace_assignments(self, user_id: UUID, data: UserAssignmentsUpdate) -> None:
        await self.session.execute(delete(UserCompany).where(UserCompany.user_id == user_id))
        await self.session.execute(delete(UserBranch).where(UserBranch.user_id == user_id))
        await self.session.execute(delete(UserRole).where(UserRole.user_id == user_id))
        self.session.add_all([UserCompany(user_id=user_id, company_id=company_id) for company_id in set(data.company_ids)])
        self.session.add_all([
            UserBranch(user_id=user_id, company_id=company_id, branch_id=branch_id)
            for company_id, branch_id in {(item.company_id, item.branch_id) for item in data.branch_assignments}
        ])
        self.session.add_all([UserRole(user_id=user_id, role_id=role_id) for role_id in set(data.role_ids)])

    async def list(
        self, actor_id: UUID, company_id: UUID | None, branch_id: UUID | None,
        search: str | None, status: str | None, page: int, page_size: int, dev: bool,
    ) -> dict:
        global_access = await self._global_access(actor_id, dev)
        if not global_access and company_id is None:
            raise HTTPException(422, "company_id is required for scoped user management.")
        rows, total = await self.repository.list(actor_id, company_id, branch_id, search, status, page, page_size, global_access)
        return {
            "items": [await self._view(user) for user in rows], "total": total, "page": page,
            "page_size": page_size, "pages": ceil(total / page_size) if total else 0,
        }

    async def create(self, data: UserCreate, actor_id: UUID, context_company: UUID | None, dev: bool) -> UserRead:
        if await self.repository.find_duplicate(data.username, data.email):
            raise HTTPException(409, "Username or email already exists.")
        await self._validate_assignments(actor_id, data.company_ids, data.branch_assignments, data.role_ids, context_company, dev)
        user = User(
            username=data.username, email=data.email, full_name=data.full_name, phone=data.phone,
            password_hash=hash_password(data.password), password_status="set",
        )
        self.session.add(user)
        await self.session.flush()
        await self._replace_assignments(user.id, UserAssignmentsUpdate(
            company_ids=data.company_ids, branch_assignments=data.branch_assignments, role_ids=data.role_ids
        ))
        await self._audit(actor_id, user.id, "USER_CREATED", {"username": user.username})
        await NotificationService(self.session).publish(
            DomainEvent(
                event_type=USER_CREATED,
                subject_id=user.id,
                user_id=user.id,
                payload={"user_id": str(user.id), "email": user.email},
            )
        )
        await self.session.commit()
        await self.session.refresh(user)
        return await self._view(user)

    async def update(self, user_id: UUID, data: UserUpdate, actor_id: UUID, context_company: UUID | None, dev: bool) -> UserRead:
        user = await self._target(user_id, actor_id, dev)
        if data.username is not None or data.email is not None:
            username = (data.username or user.username or user.email).lower()
            email = (data.email or user.email).lower()
            if await self.repository.find_duplicate(username, email, user.id):
                raise HTTPException(409, "Username or email already exists.")
            user.username, user.email = username, email
        for key in ("full_name", "phone"):
            if getattr(data, key) is not None:
                setattr(user, key, getattr(data, key))
        if data.status is not None:
            if data.status == "active":
                await self._set_active(user, True, actor_id, dev)
            else:
                await self._set_active(user, False, actor_id, dev)
                user.status = data.status
        elif data.is_active is not None:
            await self._set_active(user, data.is_active, actor_id, dev)
        if data.company_ids is not None or data.branch_assignments is not None or data.role_ids is not None:
            assignments = UserAssignmentsUpdate(
                company_ids=data.company_ids if data.company_ids is not None else await self.repository.companies(user.id),
                branch_assignments=data.branch_assignments if data.branch_assignments is not None else [
                    BranchAssignment(company_id=c, branch_id=b) for c, b in await self.repository.branches(user.id)
                ],
                role_ids=data.role_ids if data.role_ids is not None else await self.repository.roles(user.id),
            )
            await self._validate_assignments(actor_id, assignments.company_ids, assignments.branch_assignments, assignments.role_ids, context_company, dev)
            if await self._is_system_admin(user.id) and not await self._assignments_include_system_role(assignments.role_ids):
                if not await self._global_access(actor_id, dev):
                    raise HTTPException(403, "Only a global administrator can change system administrator assignments.")
                if await self._active_system_admin_count() <= 1:
                    raise HTTPException(409, "The last system administrator cannot lose administrator access.")
            await self._replace_assignments(user.id, assignments)
        await self._audit(actor_id, user.id, "USER_UPDATED", data.model_dump(exclude_unset=True))
        await self.session.commit()
        await self.session.refresh(user)
        return await self._view(user)

    async def _set_active(self, user: User, active: bool, actor_id: UUID, dev: bool) -> None:
        if not active:
            if user.id == actor_id:
                raise HTTPException(422, "You cannot deactivate your own account.")
            if await self._is_system_admin(user.id):
                count = await self._active_system_admin_count()
                if count <= 1:
                    raise HTTPException(409, "The last system administrator cannot be deactivated.")
                if not await self._global_access(actor_id, dev):
                    raise HTTPException(403, "Only a global administrator can manage system administrators.")
        user.is_active, user.status = active, "active" if active else "inactive"

    async def set_active(self, user_id: UUID, active: bool, actor_id: UUID, dev: bool) -> UserRead:
        user = await self._target(user_id, actor_id, dev)
        await self._set_active(user, active, actor_id, dev)
        await self._audit(actor_id, user.id, "USER_ACTIVATED" if active else "USER_DEACTIVATED", {})
        await self.session.commit()
        await self.session.refresh(user)
        return await self._view(user)

    async def reset_password(self, user_id: UUID, password: str | None, actor_id: UUID, dev: bool) -> str | None:
        user = await self._target(user_id, actor_id, dev)
        generated = password or secrets.token_urlsafe(16)
        if len(generated) < 12:
            generated += "A1!"
        user.password_hash, user.password_status = hash_password(generated), "set"
        sessions = await self.session.scalars(select(AuthSession).where(AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None)))
        from datetime import UTC, datetime
        for session in sessions:
            session.revoked_at = datetime.now(UTC)
        await self._audit(actor_id, user.id, "PASSWORD_RESET_BY_ADMIN", {})
        await NotificationService(self.session).publish(
            DomainEvent(
                event_type=PASSWORD_RESET,
                subject_id=user.id,
                user_id=user.id,
                payload={"user_id": str(user.id)},
            )
        )
        await self.session.commit()
        return generated if password is None else None

    async def permission_summary(self, user_id: UUID, actor_id: UUID, dev: bool) -> PermissionSummary:
        user = await self._target(user_id, actor_id, dev)
        all_permissions = sorted(await effective_permissions(self.session, user.id))
        by_company: dict[str, list[str]] = {}
        for company_id in await self.repository.companies(user.id):
            by_company[str(company_id)] = sorted(await effective_permissions(self.session, user.id, company_id))
        return PermissionSummary(permissions=all_permissions, by_company=by_company)

    async def login_history(self, user_id: UUID, actor_id: UUID, dev: bool, limit: int) -> list[LoginHistoryRead]:
        await self._target(user_id, actor_id, dev)
        return [LoginHistoryRead.model_validate(x) for x in await self.repository.login_history(user_id, limit)]

    async def audit_activity(self, user_id: UUID, actor_id: UUID, dev: bool, limit: int) -> list[AuditActivityRead]:
        await self._target(user_id, actor_id, dev)
        return [AuditActivityRead.model_validate(x) for x in await self.repository.audit_activity(user_id, limit)]

    async def _is_system_admin(self, user_id: UUID) -> bool:
        return bool(await self.session.scalar(select(Role.id).join(UserRole, UserRole.role_id == Role.id).where(
            UserRole.user_id == user_id, Role.is_system.is_(True), Role.is_active.is_(True),
            Role.status == "active",
        )))

    async def _assignments_include_system_role(self, role_ids: list[UUID]) -> bool:
        return bool(await self.session.scalar(select(Role.id).where(Role.id.in_(role_ids), Role.is_system.is_(True))))

    async def _active_system_admin_count(self) -> int:
        query = select(func.count()).select_from(User).where(
            User.is_active.is_(True),
            User.deleted_at.is_(None),
            User.id.in_(
                select(UserRole.user_id)
                .join(Role, Role.id == UserRole.role_id)
                .where(Role.is_system.is_(True), Role.is_active.is_(True), Role.status == "active")
            ),
        )
        return int(await self.session.scalar(query) or 0)
