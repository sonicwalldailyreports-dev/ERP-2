from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import RequestContext, require_permission
from app.core.dependencies import get_db_session
from app.modules.customers.schemas import (
    CustomerCreate,
    CustomerListResponse,
    CustomerRead,
    CustomerUpdate,
)
from app.modules.customers.service import CustomerService

router = APIRouter(prefix="/customers", tags=["customers"])
Session = Annotated[AsyncSession, Depends(get_db_session)]
ReadContext = Annotated[
    RequestContext, Depends(require_permission("customers.customer.view", allow_any_company=True))
]
CreateContext = Annotated[
    RequestContext, Depends(require_permission("customers.customer.create", company_param="company_id", branch_param="branch_id"))
]
ManageContext = Annotated[
    RequestContext, Depends(require_permission("customers.customer.edit", allow_any_company=True))
]
ActivateContext = Annotated[
    RequestContext, Depends(require_permission("customers.customer.activate", allow_any_company=True))
]
DeleteContext = Annotated[
    RequestContext, Depends(require_permission("customers.customer.delete", allow_any_company=True))
]


@router.get("", response_model=CustomerListResponse)
async def list_customers(
    session: Session,
    context: ReadContext,
    company_id: UUID | None = None,
    branch_id: UUID | None = None,
    search: str | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    page: int = 1,
    page_size: int = 25,
):
    return await CustomerService(session).list(
        context.user_id,
        company_id,
        branch_id,
        search,
        status_filter,
        max(1, min(page, 10000)),
        max(1, min(page_size, 100)),
        context.is_dev_context,
    )


@router.post("", response_model=CustomerRead, status_code=status.HTTP_201_CREATED)
async def create_customer(
    data: CustomerCreate,
    session: Session,
    context: CreateContext,
    company_id: UUID,
    branch_id: UUID | None = None,
):
    # In authenticated requests use the dependency's validated scope rather than
    # treating request parameters as an authority. Dev context is explicit.
    scoped_company_id = company_id if context.is_dev_context else context.company_id
    scoped_branch_id = branch_id if context.is_dev_context else context.branch_id
    if scoped_company_id is None:
        raise HTTPException(status_code=422, detail="company_id is required.")
    return await CustomerService(session).create(data, scoped_company_id, scoped_branch_id, context.user_id)


@router.get("/{customer_id}", response_model=CustomerRead)
async def get_customer(customer_id: UUID, session: Session, context: ReadContext):
    return await CustomerService(session)._target(customer_id, context.user_id, context.is_dev_context)


@router.patch("/{customer_id}", response_model=CustomerRead)
async def update_customer(
    customer_id: UUID, data: CustomerUpdate, session: Session, context: ManageContext
):
    return await CustomerService(session).update(customer_id, data, context.user_id, context.is_dev_context)


@router.post("/{customer_id}/activate", response_model=CustomerRead)
async def activate_customer(customer_id: UUID, session: Session, context: ActivateContext):
    return await CustomerService(session).set_active(customer_id, True, context.user_id, context.is_dev_context)


@router.post("/{customer_id}/deactivate", response_model=CustomerRead)
async def deactivate_customer(customer_id: UUID, session: Session, context: ActivateContext):
    return await CustomerService(session).set_active(customer_id, False, context.user_id, context.is_dev_context)


@router.delete("/{customer_id}", response_model=CustomerRead)
async def delete_customer(customer_id: UUID, session: Session, context: DeleteContext):
    return await CustomerService(session).delete(customer_id, context.user_id, context.is_dev_context)
