from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import RequestContext, require_permission
from app.core.dependencies import get_db_session
from app.modules.transactions.schemas import (
    TransactionCreate,
    TransactionRead,
    TransactionReverse,
)
from app.modules.transactions.service import (
    FinancialTransactionError,
    FinancialTransactionService,
    TransactionAuthorizationError,
    TransactionNotFoundError,
    TransactionValidationError,
)

router = APIRouter(prefix="/transactions", tags=["transactions"])
Session = Annotated[AsyncSession, Depends(get_db_session)]
Read = Annotated[RequestContext, Depends(require_permission("transactions.transaction.view", allow_any_company=True))]
Create = Annotated[RequestContext, Depends(require_permission("transactions.transaction.create", allow_any_company=True))]
Post = Annotated[RequestContext, Depends(require_permission("transactions.transaction.post", allow_any_company=True))]
Reverse = Annotated[RequestContext, Depends(require_permission("transactions.transaction.reverse", allow_any_company=True))]


def _company(context: RequestContext, company_id: UUID | None) -> UUID:
    value = company_id if context.is_dev_context else context.company_id
    if value is None:
        raise HTTPException(status_code=422, detail="company_id is required.")
    return value


def _error(error: FinancialTransactionError) -> HTTPException:
    if isinstance(error, TransactionAuthorizationError):
        return HTTPException(status_code=403, detail=str(error))
    if isinstance(error, TransactionNotFoundError):
        return HTTPException(status_code=404, detail=str(error))
    if isinstance(error, TransactionValidationError):
        return HTTPException(status_code=422, detail=str(error))
    return HTTPException(status_code=409, detail=str(error))


@router.get("", response_model=list[TransactionRead])
async def list_transactions(
    session: Session,
    context: Read,
    company_id: UUID | None = None,
    branch_id: UUID | None = None,
    transaction_status: str | None = Query(default=None, alias="status"),
    start_date: date | None = None,
    end_date: date | None = None,
):
    return await FinancialTransactionService(session).list(
        _company(context, company_id),
        branch_id if context.is_dev_context else context.branch_id,
        transaction_status,
        start_date,
        end_date,
    )


@router.post("", response_model=TransactionRead, status_code=status.HTTP_201_CREATED)
async def create_transaction(data: TransactionCreate, session: Session, context: Create):
    try:
        return await FinancialTransactionService(session).create(
            data, context.user_id, context.is_dev_context
        )
    except FinancialTransactionError as error:
        raise _error(error) from error


@router.get("/{transaction_id}", response_model=TransactionRead)
async def get_transaction(transaction_id: UUID, session: Session, context: Read):
    try:
        return await FinancialTransactionService(session).get(
            transaction_id,
            context.user_id,
            permission_code="transactions.transaction.view",
            is_dev_context=context.is_dev_context,
        )
    except FinancialTransactionError as error:
        raise _error(error) from error


@router.post("/{transaction_id}/post", response_model=TransactionRead)
async def post_transaction(transaction_id: UUID, session: Session, context: Post):
    try:
        return await FinancialTransactionService(session).post(
            transaction_id, context.user_id, context.is_dev_context
        )
    except FinancialTransactionError as error:
        raise _error(error) from error


@router.post("/{transaction_id}/reverse", response_model=TransactionRead, status_code=status.HTTP_201_CREATED)
async def reverse_transaction(
    transaction_id: UUID,
    session: Session,
    context: Reverse,
    data: TransactionReverse | None = None,
):
    try:
        return await FinancialTransactionService(session).reverse(
            transaction_id,
            context.user_id,
            reference=data.reference if data else None,
            description=data.description if data else None,
            is_dev_context=context.is_dev_context,
        )
    except FinancialTransactionError as error:
        raise _error(error) from error
