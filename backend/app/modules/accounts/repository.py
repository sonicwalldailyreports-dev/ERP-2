from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Account, AccountType, Branch, Company
from app.modules.accounts.schemas import ACCOUNT_TYPE_CODES


class AccountRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_types(self, company_id: UUID | None = None) -> list[AccountType]:
        existing_codes = set(
            await self.session.scalars(
                select(AccountType.code).where(AccountType.company_id.is_(None))
            )
        )
        missing = [
            AccountType(
                code=code,
                name=code.title(),
                description=f"{code.title()} account",
                is_system=True,
            )
            for code in ACCOUNT_TYPE_CODES
            if code not in existing_codes
        ]
        if missing:
            self.session.add_all(missing)
            await self.session.commit()
        result = await self.session.scalars(
            select(AccountType)
            .where(
                AccountType.is_active.is_(True),
                or_(AccountType.company_id.is_(None), AccountType.company_id == company_id),
            )
            .order_by(AccountType.name)
        )
        return list(result)

    async def get_type(self, type_id: UUID, company_id: UUID) -> AccountType | None:
        return await self.session.scalar(
            select(AccountType).where(
                AccountType.id == type_id,
                AccountType.is_active.is_(True),
                or_(AccountType.company_id.is_(None), AccountType.company_id == company_id),
            )
        )

    async def get(self, account_id: UUID) -> Account | None:
        return await self.session.scalar(
            select(Account).where(Account.id == account_id, Account.deleted_at.is_(None))
        )

    async def list(
        self,
        company_id: UUID,
        branch_id: UUID | None,
        search: str | None,
        active_only: bool = False,
    ) -> list[Account]:
        query = select(Account).where(
            Account.company_id == company_id,
            Account.deleted_at.is_(None),
            (Account.branch_id.is_(None) if branch_id is None else Account.branch_id == branch_id),
        )
        if search:
            term = f"%{search.strip()}%"
            query = query.where(or_(Account.account_code.ilike(term), Account.name.ilike(term)))
        if active_only:
            query = query.where(Account.is_active.is_(True))
        return list(await self.session.scalars(query.order_by(Account.account_code)))

    async def code_exists(self, company_id: UUID, code: str, exclude_id: UUID | None = None) -> bool:
        query = select(func.count(Account.id)).where(
            Account.company_id == company_id,
            Account.account_code == code,
            Account.deleted_at.is_(None),
        )
        if exclude_id is not None:
            query = query.where(Account.id != exclude_id)
        return bool(await self.session.scalar(query))

    async def valid_company(self, company_id: UUID) -> bool:
        return bool(await self.session.scalar(select(Company.id).where(Company.id == company_id)))

    async def valid_branch(self, company_id: UUID, branch_id: UUID) -> bool:
        return bool(
            await self.session.scalar(
                select(Branch.id).where(Branch.id == branch_id, Branch.company_id == company_id)
            )
        )
