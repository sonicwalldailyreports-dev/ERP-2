from __future__ import annotations

import json
from datetime import UTC, datetime
from math import ceil
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import has_permission
from app.db.models import AuditLog, Vendor
from app.modules.vendors.repository import VendorRepository
from app.modules.vendors.schemas import VendorCreate, VendorUpdate


class VendorService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repository = VendorRepository(session)

    async def _audit(self, actor_id: UUID, vendor: Vendor, action: str, details: dict) -> None:
        self.session.add(
            AuditLog(
                user_id=actor_id,
                company_id=vendor.company_id,
                branch_id=vendor.branch_id,
                action=action,
                entity_type="vendor",
                entity_id=vendor.id,
                details=json.dumps(details, default=str),
            )
        )

    async def _target(
        self, vendor_id: UUID, actor_id: UUID, dev: bool, permission: str = "vendors.vendor.view"
    ) -> Vendor:
        vendor = await self.repository.get(vendor_id)
        if vendor is None:
            raise HTTPException(status_code=404, detail="Vendor not found.")
        if not dev and not await has_permission(
            self.session, actor_id, permission, vendor.company_id, vendor.branch_id
        ):
            raise HTTPException(status_code=403, detail="Organization scope is not allowed.")
        return vendor

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
            raise HTTPException(status_code=422, detail="company_id is required for scoped vendor management.")
        if not dev and company_id is not None and not await has_permission(
            self.session, actor_id, "vendors.vendor.view", company_id, branch_id
        ):
            raise HTTPException(status_code=403, detail="Organization scope is not allowed.")
        rows, total = await self.repository.list(company_id, branch_id, search, status_filter, page, page_size)
        return {
            "items": rows,
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": ceil(total / page_size) if total else 0,
        }

    async def create(
        self, data: VendorCreate, company_id: UUID, branch_id: UUID | None, actor_id: UUID
    ) -> Vendor:
        if await self.repository.valid_company(company_id) is None:
            raise HTTPException(status_code=404, detail="Company not found.")
        if branch_id is not None and await self.repository.valid_branch(company_id, branch_id) is None:
            raise HTTPException(status_code=404, detail="Branch not found for this company.")
        if await self.repository.find_code(company_id, data.vendor_code):
            raise HTTPException(status_code=409, detail="Vendor code already exists in this company.")
        values = data.model_dump(exclude={"vendor_name", "address"})
        if data.vendor_name is not None:
            values["name"] = data.vendor_name
        if data.address is not None:
            values["address_line1"] = data.address
        vendor = Vendor(**values, company_id=company_id, branch_id=branch_id)
        self.session.add(vendor)
        try:
            await self.session.flush()
        except IntegrityError:
            await self.session.rollback()
            raise HTTPException(status_code=409, detail="Vendor code already exists in this company.") from None
        await self._audit(actor_id, vendor, "VENDOR_CREATED", {"vendor_code": vendor.vendor_code})
        await self.session.commit()
        await self.session.refresh(vendor)
        return vendor

    async def update(self, vendor_id: UUID, data: VendorUpdate, actor_id: UUID, dev: bool) -> Vendor:
        vendor = await self._target(vendor_id, actor_id, dev, "vendors.vendor.edit")
        values = data.model_dump(exclude_unset=True, exclude={"vendor_name", "address"})
        if data.vendor_name is not None:
            values["name"] = data.vendor_name
        if data.address is not None:
            values["address_line1"] = data.address
        if "vendor_code" in values and await self.repository.find_code(
            vendor.company_id, values["vendor_code"], vendor.id
        ):
            raise HTTPException(status_code=409, detail="Vendor code already exists in this company.")
        for key, value in values.items():
            setattr(vendor, key, value)
        if data.status is not None:
            vendor.is_active = data.status == "active"
        elif data.is_active is not None:
            vendor.status = "active" if data.is_active else "inactive"
        try:
            await self.session.flush()
        except IntegrityError:
            await self.session.rollback()
            raise HTTPException(status_code=409, detail="Vendor code already exists in this company.") from None
        await self._audit(actor_id, vendor, "VENDOR_UPDATED", values)
        await self.session.commit()
        await self.session.refresh(vendor)
        return vendor

    async def set_active(self, vendor_id: UUID, active: bool, actor_id: UUID, dev: bool) -> Vendor:
        vendor = await self._target(vendor_id, actor_id, dev, "vendors.vendor.activate")
        vendor.is_active = active
        vendor.status = "active" if active else "inactive"
        await self._audit(
            actor_id, vendor, "VENDOR_ACTIVATED" if active else "VENDOR_DEACTIVATED", {}
        )
        await self.session.commit()
        await self.session.refresh(vendor)
        return vendor

    async def delete(self, vendor_id: UUID, actor_id: UUID, dev: bool) -> Vendor:
        vendor = await self._target(vendor_id, actor_id, dev, "vendors.vendor.delete")
        vendor.deleted_at = datetime.now(UTC)
        vendor.is_active = False
        vendor.status = "inactive"
        await self._audit(actor_id, vendor, "VENDOR_DELETED", {})
        await self.session.commit()
        await self.session.refresh(vendor)
        return vendor
