from __future__ import annotations

import json
from datetime import UTC, datetime
from math import ceil
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import has_permission
from app.db.models import AuditLog, Customer
from app.modules.customers.repository import CustomerRepository
from app.modules.customers.schemas import CustomerCreate, CustomerUpdate


class CustomerService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repository = CustomerRepository(session)

    async def _audit(self, actor_id: UUID, customer: Customer, action: str, details: dict) -> None:
        self.session.add(
            AuditLog(
                user_id=actor_id,
                company_id=customer.company_id,
                branch_id=customer.branch_id,
                action=action,
                entity_type="customer",
                entity_id=customer.id,
                details=json.dumps(details, default=str),
            )
        )

    async def _target(
        self, customer_id: UUID, actor_id: UUID, dev: bool, permission: str = "customers.customer.view"
    ) -> Customer:
        customer = await self.repository.get(customer_id)
        if customer is None:
            raise HTTPException(status_code=404, detail="Customer not found.")
        if not dev and not await has_permission(
            self.session, actor_id, permission, customer.company_id, customer.branch_id
        ):
            raise HTTPException(status_code=403, detail="Organization scope is not allowed.")
        return customer

    async def list(
        self,
        actor_id: UUID,
        company_id: UUID | None,
        branch_id: UUID | None,
        search: str | None,
        status_filter: str | None,
        page: int,
        page_size: int,
        dev: bool,
    ) -> dict:
        if not dev and company_id is None:
            raise HTTPException(status_code=422, detail="company_id is required for scoped customer management.")
        rows, total = await self.repository.list(company_id, branch_id, search, status_filter, page, page_size)
        if not dev and company_id is not None and not await has_permission(
            self.session, actor_id, "customers.customer.view", company_id, branch_id
        ):
            # The permission dependency validates the requested scope. This second
            # check prevents a future caller from bypassing it when using the service.
            raise HTTPException(status_code=403, detail="Organization scope is not allowed.")
        return {
            "items": rows,
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": ceil(total / page_size) if total else 0,
        }

    async def create(
        self, data: CustomerCreate, company_id: UUID, branch_id: UUID | None, actor_id: UUID
    ) -> Customer:
        if await self.repository.valid_company(company_id) is None:
            raise HTTPException(status_code=404, detail="Company not found.")
        if branch_id is not None and await self.repository.valid_branch(company_id, branch_id) is None:
            raise HTTPException(status_code=404, detail="Branch not found for this company.")
        if await self.repository.find_code(company_id, data.customer_code):
            raise HTTPException(status_code=409, detail="Customer code already exists in this company.")
        values = data.model_dump(exclude={"customer_name", "address"})
        if data.customer_name is not None:
            values["name"] = data.customer_name
        if data.address is not None:
            values["address_line1"] = data.address
        customer = Customer(**values, company_id=company_id, branch_id=branch_id)
        self.session.add(customer)
        try:
            await self.session.flush()
        except IntegrityError:
            await self.session.rollback()
            raise HTTPException(status_code=409, detail="Customer code already exists in this company.") from None
        await self._audit(actor_id, customer, "CUSTOMER_CREATED", {"customer_code": customer.customer_code})
        await self.session.commit()
        await self.session.refresh(customer)
        return customer

    async def update(self, customer_id: UUID, data: CustomerUpdate, actor_id: UUID, dev: bool) -> Customer:
        customer = await self._target(customer_id, actor_id, dev, "customers.customer.edit")
        values = data.model_dump(exclude_unset=True, exclude={"address"})
        if values.pop("customer_name", None) is not None:
            values["name"] = data.customer_name
        if data.address is not None:
            values["address_line1"] = data.address
        if "customer_code" in values and await self.repository.find_code(
            customer.company_id, values["customer_code"], customer.id
        ):
            raise HTTPException(status_code=409, detail="Customer code already exists in this company.")
        for key, value in values.items():
            setattr(customer, key, value)
        if data.status is not None:
            customer.is_active = data.status == "active"
        elif data.is_active is not None:
            customer.status = "active" if data.is_active else "inactive"
        try:
            await self.session.flush()
        except IntegrityError:
            await self.session.rollback()
            raise HTTPException(status_code=409, detail="Customer code already exists in this company.") from None
        await self._audit(actor_id, customer, "CUSTOMER_UPDATED", values)
        await self.session.commit()
        await self.session.refresh(customer)
        return customer

    async def set_active(self, customer_id: UUID, active: bool, actor_id: UUID, dev: bool) -> Customer:
        customer = await self._target(customer_id, actor_id, dev, "customers.customer.activate")
        customer.is_active = active
        customer.status = "active" if active else "inactive"
        await self._audit(
            actor_id, customer, "CUSTOMER_ACTIVATED" if active else "CUSTOMER_DEACTIVATED", {}
        )
        await self.session.commit()
        await self.session.refresh(customer)
        return customer

    async def delete(self, customer_id: UUID, actor_id: UUID, dev: bool) -> Customer:
        customer = await self._target(customer_id, actor_id, dev, "customers.customer.delete")
        customer.deleted_at = datetime.now(UTC)
        customer.is_active = False
        customer.status = "inactive"
        await self._audit(actor_id, customer, "CUSTOMER_DELETED", {})
        await self.session.commit()
        return customer
