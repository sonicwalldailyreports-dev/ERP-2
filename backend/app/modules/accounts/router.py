from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import RequestContext, require_permission
from app.core.dependencies import get_db_session
from app.modules.accounts.schemas import AccountCreate, AccountRead, AccountTypeRead, AccountUpdate
from app.modules.accounts.service import AccountService

router = APIRouter(prefix="/accounts", tags=["accounts"])
account_types_router = APIRouter(prefix="/account-types", tags=["accounts"])
Session = Annotated[AsyncSession, Depends(get_db_session)]
ReadContext = Annotated[
    RequestContext, Depends(require_permission("accounts.account.view", allow_any_company=True))
]
ManageContext = Annotated[
    RequestContext, Depends(require_permission("accounts.account.edit", allow_any_company=True))
]
CreateContext = Annotated[
    RequestContext, Depends(require_permission("accounts.account.create", allow_any_company=True))
]
ActivateContext = Annotated[
    RequestContext, Depends(require_permission("accounts.account.activate", allow_any_company=True))
]
DeleteContext = Annotated[
    RequestContext, Depends(require_permission("accounts.account.delete", allow_any_company=True))
]


@router.get("/types", response_model=list[AccountTypeRead])
async def list_account_types(
    session: Session, context: ReadContext, company_id: UUID | None = None
):
    if not context.is_dev_context and company_id is None:
        company_id = context.company_id
    return await AccountService(session).list_types(company_id)


@account_types_router.get("", response_model=list[AccountTypeRead])
async def list_account_types_root(
    session: Session, context: ReadContext, company_id: UUID | None = None
):
    if not context.is_dev_context and company_id is None:
        company_id = context.company_id
    return await AccountService(session).list_types(company_id)


@router.get("", response_model=list[AccountRead])
async def list_accounts(
    session: Session,
    context: ReadContext,
    company_id: UUID | None = None,
    branch_id: UUID | None = None,
    search: str | None = None,
    active_only: bool = Query(False),
):
    scoped_company = company_id if context.is_dev_context else context.company_id
    scoped_branch = branch_id if context.is_dev_context else context.branch_id
    if scoped_company is None:
        raise HTTPException(status_code=422, detail="company_id is required.")
    return await AccountService(session).list(scoped_company, scoped_branch, search, active_only)


@router.post("", response_model=AccountRead, status_code=status.HTTP_201_CREATED)
async def create_account(data: AccountCreate, session: Session, context: CreateContext):
    return await AccountService(session).create(data, context.user_id, context.is_dev_context)


@router.get("/{account_id}", response_model=AccountRead)
async def get_account(account_id: UUID, session: Session, context: ReadContext):
    account = await AccountService(session)._target(
        account_id, context.user_id, context.is_dev_context, "accounts.account.view"
    )
    return account


@router.patch("/{account_id}", response_model=AccountRead)
async def update_account(
    account_id: UUID, data: AccountUpdate, session: Session, context: ManageContext
):
    return await AccountService(session).update(account_id, data, context.user_id, context.is_dev_context)


@router.post("/{account_id}/activate", response_model=AccountRead)
async def activate_account(account_id: UUID, session: Session, context: ActivateContext):
    return await AccountService(session).set_active(account_id, True, context.user_id, context.is_dev_context)


@router.post("/{account_id}/deactivate", response_model=AccountRead)
async def deactivate_account(account_id: UUID, session: Session, context: ActivateContext):
    return await AccountService(session).set_active(account_id, False, context.user_id, context.is_dev_context)


@router.delete("/{account_id}", response_model=AccountRead)
async def delete_account(account_id: UUID, session: Session, context: DeleteContext):
    return await AccountService(session).delete(account_id, context.user_id, context.is_dev_context)
