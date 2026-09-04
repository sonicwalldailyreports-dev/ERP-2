from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import RequestContext, require_permission
from app.core.dependencies import get_db_session
from app.modules.vendors.schemas import VendorCreate, VendorListResponse, VendorRead, VendorUpdate
from app.modules.vendors.service import VendorService

router = APIRouter(prefix="/vendors", tags=["vendors"])
Session = Annotated[AsyncSession, Depends(get_db_session)]
ReadContext = Annotated[
    RequestContext, Depends(require_permission("vendors.vendor.view", allow_any_company=True))
]
CreateContext = Annotated[
    RequestContext,
    Depends(require_permission("vendors.vendor.create", company_param="company_id", branch_param="branch_id")),
]
ManageContext = Annotated[
    RequestContext, Depends(require_permission("vendors.vendor.edit", allow_any_company=True))
]
ActivateContext = Annotated[
    RequestContext, Depends(require_permission("vendors.vendor.activate", allow_any_company=True))
]
DeleteContext = Annotated[
    RequestContext, Depends(require_permission("vendors.vendor.delete", allow_any_company=True))
]


@router.get("", response_model=VendorListResponse)
async def list_vendors(
    session: Session,
    context: ReadContext,
    company_id: UUID | None = None,
    branch_id: UUID | None = None,
    search: str | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    page: int = 1,
    page_size: int = 25,
):
    return await VendorService(session).list(
        context.user_id,
        company_id,
        branch_id,
        search,
        status_filter,
        max(1, min(page, 10000)),
        max(1, min(page_size, 100)),
        context.is_dev_context,
    )


@router.post("", response_model=VendorRead, status_code=status.HTTP_201_CREATED)
async def create_vendor(
    data: VendorCreate,
    session: Session,
    context: CreateContext,
    company_id: UUID,
    branch_id: UUID | None = None,
):
    scoped_company_id = company_id if context.is_dev_context else context.company_id
    scoped_branch_id = branch_id if context.is_dev_context else context.branch_id
    if scoped_company_id is None:
        raise HTTPException(status_code=422, detail="company_id is required.")
    return await VendorService(session).create(data, scoped_company_id, scoped_branch_id, context.user_id)


@router.get("/{vendor_id}", response_model=VendorRead)
async def get_vendor(vendor_id: UUID, session: Session, context: ReadContext):
    return await VendorService(session)._target(vendor_id, context.user_id, context.is_dev_context)


@router.patch("/{vendor_id}", response_model=VendorRead)
async def update_vendor(vendor_id: UUID, data: VendorUpdate, session: Session, context: ManageContext):
    return await VendorService(session).update(vendor_id, data, context.user_id, context.is_dev_context)


@router.post("/{vendor_id}/activate", response_model=VendorRead)
async def activate_vendor(vendor_id: UUID, session: Session, context: ActivateContext):
    return await VendorService(session).set_active(vendor_id, True, context.user_id, context.is_dev_context)


@router.post("/{vendor_id}/deactivate", response_model=VendorRead)
async def deactivate_vendor(vendor_id: UUID, session: Session, context: ActivateContext):
    return await VendorService(session).set_active(vendor_id, False, context.user_id, context.is_dev_context)


@router.delete("/{vendor_id}", response_model=VendorRead)
async def delete_vendor(vendor_id: UUID, session: Session, context: DeleteContext):
    return await VendorService(session).delete(vendor_id, context.user_id, context.is_dev_context)
