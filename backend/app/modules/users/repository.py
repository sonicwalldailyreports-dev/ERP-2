from __future__ import annotations

from builtins import list as builtin_list
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    AuditLog,
    Branch,
    Company,
    LoginHistory,
    Role,
    User,
    UserBranch,
    UserCompany,
    UserRole,
)


class UserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, user_id: UUID) -> User | None:
        return await self.session.scalar(select(User).where(User.id == user_id, User.deleted_at.is_(None)))

    async def find_duplicate(self, username: str, email: str, exclude_id: UUID | None = None) -> User | None:
        query = select(User).where(
            or_(User.username == username.lower(), User.email == email.lower()), User.deleted_at.is_(None)
        )
        if exclude_id is not None:
            query = query.where(User.id != exclude_id)
        return await self.session.scalar(query)

    async def list(
        self, actor_id: UUID, company_id: UUID | None, branch_id: UUID | None,
        search: str | None, status: str | None, page: int, page_size: int, global_access: bool,
    ) -> tuple[builtin_list[User], int]:
        query = select(User).where(User.deleted_at.is_(None))
        if not global_access or company_id is not None:
            query = query.join(UserCompany, UserCompany.user_id == User.id).where(
                UserCompany.company_id == company_id
            )
        if branch_id is not None:
            query = query.join(UserBranch, UserBranch.user_id == User.id).where(
                UserBranch.branch_id == branch_id, UserBranch.company_id == company_id
            )
        if search:
            term = f"%{search.lower()}%"
            query = query.where(
                or_(func.lower(User.username).like(term), func.lower(User.email).like(term),
                    func.lower(User.full_name).like(term), func.lower(User.phone).like(term))
            )
        if status:
            query = query.where(User.status == status)
        query = query.distinct()
        total = int(await self.session.scalar(select(func.count()).select_from(query.subquery())) or 0)
        rows = list(await self.session.scalars(
            query.order_by(User.full_name, User.email).offset((page - 1) * page_size).limit(page_size)
        ))
        return rows, total

    async def companies(self, user_id: UUID) -> builtin_list[UUID]:
        return list(await self.session.scalars(
            select(UserCompany.company_id).where(UserCompany.user_id == user_id).order_by(UserCompany.company_id)
        ))

    async def branches(self, user_id: UUID) -> builtin_list[tuple[UUID, UUID]]:
        return list(await self.session.execute(
            select(UserBranch.company_id, UserBranch.branch_id).where(UserBranch.user_id == user_id)
        ))

    async def roles(self, user_id: UUID) -> builtin_list[UUID]:
        return list(await self.session.scalars(
            select(UserRole.role_id).where(UserRole.user_id == user_id).order_by(UserRole.role_id)
        ))

    async def login_history(self, user_id: UUID, limit: int) -> builtin_list[LoginHistory]:
        return list(await self.session.scalars(
            select(LoginHistory).where(LoginHistory.user_id == user_id)
            .order_by(LoginHistory.created_at.desc()).limit(limit)
        ))

    async def audit_activity(self, user_id: UUID, limit: int) -> builtin_list[AuditLog]:
        return list(await self.session.scalars(
            select(AuditLog).where(AuditLog.entity_type == "user", AuditLog.entity_id == user_id)
            .order_by(AuditLog.created_at.desc()).limit(limit)
        ))

    async def valid_company(self, company_id: UUID) -> Company | None:
        return await self.session.scalar(select(Company).where(Company.id == company_id, Company.is_active.is_(True)))

    async def valid_branch(self, company_id: UUID, branch_id: UUID) -> Branch | None:
        return await self.session.scalar(select(Branch).where(
            Branch.id == branch_id, Branch.company_id == company_id, Branch.is_active.is_(True)
        ))

    async def valid_role(self, role_id: UUID) -> Role | None:
        return await self.session.scalar(select(Role).where(Role.id == role_id, Role.is_active.is_(True), Role.status == "active"))
