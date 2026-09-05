from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import has_permission
from app.db.models import Account, AccountType, AuditLog
from app.modules.accounts.repository import AccountRepository
from app.modules.accounts.schemas import AccountCreate, AccountUpdate


class AccountService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repository = AccountRepository(session)

    async def list_types(self, company_id: UUID | None = None) -> list[AccountType]:
        return await self.repository.list_types(company_id)

    async def list(
        self,
        company_id: UUID,
        branch_id: UUID | None,
        search: str | None,
        active_only: bool,
    ) -> list[Account]:
        if not await self.repository.valid_company(company_id):
            raise HTTPException(status_code=404, detail="Company not found.")
        if branch_id is not None and not await self.repository.valid_branch(company_id, branch_id):
            raise HTTPException(status_code=404, detail="Branch not found for this company.")
        return await self.repository.list(company_id, branch_id, search, active_only)

    async def _target(self, account_id: UUID, actor_id: UUID, dev: bool, permission: str) -> Account:
        account = await self.repository.get(account_id)
        if account is None:
            raise HTTPException(status_code=404, detail="Account not found.")
        if not dev and not await has_permission(
            self.session, actor_id, permission, account.company_id, account.branch_id
        ):
            raise HTTPException(status_code=403, detail="Organization scope is not allowed.")
        return account

    async def create(self, data: AccountCreate, actor_id: UUID, dev: bool) -> Account:
        if not await self.repository.valid_company(data.company_id):
            raise HTTPException(status_code=404, detail="Company not found.")
        if data.branch_id is not None and not await self.repository.valid_branch(data.company_id, data.branch_id):
            raise HTTPException(status_code=404, detail="Branch not found for this company.")
        if not dev and not await has_permission(
            self.session, actor_id, "accounts.account.create", data.company_id, data.branch_id
        ):
            raise HTTPException(status_code=403, detail="Organization scope is not allowed.")
        if await self.repository.code_exists(data.company_id, data.account_code):
            raise HTTPException(status_code=409, detail="Account code already exists in this company.")
        account_type = await self.repository.get_type(data.account_type_id, data.company_id)
        if account_type is None:
            raise HTTPException(status_code=422, detail="Account type is not valid for this company.")
        await self._validate_parent(data.company_id, data.parent_account_id, data.is_group)
        account = Account(**data.model_dump())
        self.session.add(account)
        try:
            await self.session.flush()
        except IntegrityError:
            await self.session.rollback()
            raise HTTPException(status_code=409, detail="Account code already exists in this company.") from None
        await self._audit(account, actor_id, "ACCOUNT_CREATED")
        await self.session.commit()
        await self.session.refresh(account)
        return account

    async def update(self, account_id: UUID, data: AccountUpdate, actor_id: UUID, dev: bool) -> Account:
        account = await self._target(account_id, actor_id, dev, "accounts.account.edit")
        values = data.model_dump(exclude_unset=True)
        company_id = account.company_id
        if "branch_id" in values and values["branch_id"] is not None and not await self.repository.valid_branch(
            company_id, values["branch_id"]
        ):
            raise HTTPException(status_code=404, detail="Branch not found for this company.")
        if "account_code" in values and await self.repository.code_exists(company_id, values["account_code"], account.id):
            raise HTTPException(status_code=409, detail="Account code already exists in this company.")
        type_id = values.get("account_type_id", account.account_type_id)
        if await self.repository.get_type(type_id, company_id) is None:
            raise HTTPException(status_code=422, detail="Account type is not valid for this company.")
        parent_id = values.get("parent_account_id", account.parent_account_id)
        is_group = values.get("is_group", account.is_group)
        await self._validate_parent(company_id, parent_id, is_group, account.id)
        for key, value in values.items():
            setattr(account, key, value)
        await self._audit(account, actor_id, "ACCOUNT_UPDATED", values)
        try:
            await self.session.commit()
        except IntegrityError:
            await self.session.rollback()
            raise HTTPException(status_code=409, detail="Account code already exists in this company.") from None
        await self.session.refresh(account)
        return account

    async def set_active(self, account_id: UUID, active: bool, actor_id: UUID, dev: bool) -> Account:
        account = await self._target(account_id, actor_id, dev, "accounts.account.activate")
        account.is_active = active
        await self._audit(account, actor_id, "ACCOUNT_ACTIVATED" if active else "ACCOUNT_DEACTIVATED")
        await self.session.commit()
        await self.session.refresh(account)
        return account

    async def delete(self, account_id: UUID, actor_id: UUID, dev: bool) -> Account:
        account = await self._target(account_id, actor_id, dev, "accounts.account.delete")
        account.deleted_at = datetime.now(UTC)
        account.is_active = False
        await self._audit(account, actor_id, "ACCOUNT_DELETED")
        await self.session.commit()
        return account

    async def _validate_parent(
        self, company_id: UUID, parent_id: UUID | None, is_group: bool, account_id: UUID | None = None
    ) -> None:
        if parent_id is None:
            return
        parent = await self.repository.get(parent_id)
        if parent is None or parent.company_id != company_id:
            raise HTTPException(status_code=422, detail="Parent account must belong to the same company.")
        if not parent.is_group:
            raise HTTPException(status_code=422, detail="Parent account must be a group account.")
        if account_id is not None and parent.id == account_id:
            raise HTTPException(status_code=422, detail="An account cannot be its own parent.")
        current = parent
        seen = {account_id} if account_id else set()
        while current.parent_account_id is not None:
            if current.parent_account_id in seen:
                raise HTTPException(status_code=422, detail="Account hierarchy cannot contain cycles.")
            seen.add(current.id)
            current = await self.repository.get(current.parent_account_id)
            if current is None:
                break

    async def _audit(
        self, account: Account, actor_id: UUID, action: str, details: dict | None = None
    ) -> None:
        self.session.add(
            AuditLog(
                company_id=account.company_id,
                branch_id=account.branch_id,
                user_id=actor_id,
                action=action,
                entity_type="account",
                entity_id=account.id,
                details=json.dumps(details or {"account_code": account.account_code}),
            )
        )
