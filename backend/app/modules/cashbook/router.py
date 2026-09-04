from datetime import UTC, date, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import RequestContext, require_permission
from app.core.dependencies import get_db_session
from app.modules.cashbook.schemas import (
    CashAccountCreate,
    CashAccountRead,
    CashAccountUpdate,
    CashTransactionCreate,
    CashTransactionRead,
    CashTransactionUpdate,
    DailySummaryRead,
    OpeningBalanceCreate,
    OpeningBalanceRead,
    TransactionCancel,
    TransactionReject,
)
from app.modules.cashbook.service import CashBookService

router = APIRouter(prefix="/cash-book", tags=["cash-book"])
Session = Annotated[AsyncSession, Depends(get_db_session)]
Read = Annotated[RequestContext, Depends(require_permission("cashbook.transaction.view", allow_any_company=True))]
AccountRead = Annotated[RequestContext, Depends(require_permission("cashbook.account.view", allow_any_company=True))]
AccountCreateContext = Annotated[RequestContext, Depends(require_permission("cashbook.account.create", allow_any_company=True))]
AccountEditContext = Annotated[RequestContext, Depends(require_permission("cashbook.account.edit", allow_any_company=True))]
Create = Annotated[RequestContext, Depends(require_permission("cashbook.transaction.create", company_param="company_id", branch_param="branch_id", allow_any_company=True))]
Submit = Annotated[RequestContext, Depends(require_permission("cashbook.transaction.submit", allow_any_company=True))]
Approve = Annotated[RequestContext, Depends(require_permission("cashbook.transaction.approve", allow_any_company=True))]
Post = Annotated[RequestContext, Depends(require_permission("cashbook.transaction.post", allow_any_company=True))]
Reject = Annotated[RequestContext, Depends(require_permission("cashbook.transaction.reject", allow_any_company=True))]
Cancel = Annotated[RequestContext, Depends(require_permission("cashbook.transaction.cancel", allow_any_company=True))]
Reverse = Annotated[RequestContext, Depends(require_permission("cashbook.transaction.reverse", allow_any_company=True))]
Summary = Annotated[RequestContext, Depends(require_permission("cashbook.summary.view", allow_any_company=True))]


def _company(context: RequestContext, company_id: UUID | None) -> UUID:
    value = company_id if context.is_dev_context else context.company_id
    if value is None:
        raise HTTPException(status_code=422, detail="company_id is required.")
    return value


@router.get("/accounts", response_model=list[CashAccountRead])
async def list_accounts(session: Session, context: AccountRead, company_id: UUID | None = None, branch_id: UUID | None = None):
    service = CashBookService(session)
    return [await service.account_payload(account) for account in await service.list_accounts(_company(context, company_id), branch_id if context.is_dev_context else context.branch_id)]


@router.post("/accounts", response_model=CashAccountRead, status_code=status.HTTP_201_CREATED)
async def create_account(data: CashAccountCreate, session: Session, context: AccountCreateContext):
    service = CashBookService(session)
    return await service.account_payload(await service.create_account(data, context.user_id, context.is_dev_context))


@router.get("/accounts/{account_id}", response_model=CashAccountRead)
async def get_account(account_id: UUID, session: Session, context: AccountRead):
    service = CashBookService(session)
    account = await service.account(account_id)
    await service._allowed(context.user_id, "cashbook.account.view", account.company_id, account.branch_id, context.is_dev_context)
    return await service.account_payload(account)


@router.patch("/accounts/{account_id}", response_model=CashAccountRead)
async def update_account(account_id: UUID, data: CashAccountUpdate, session: Session, context: AccountEditContext):
    service = CashBookService(session)
    return await service.account_payload(await service.update_account(account_id, data, context.user_id, context.is_dev_context))


@router.post("/opening-balances", response_model=OpeningBalanceRead)
async def opening_balance(data: OpeningBalanceCreate, session: Session, context: Annotated[RequestContext, Depends(require_permission("cashbook.opening_balance.manage", allow_any_company=True))]):
    return await CashBookService(session).set_opening_balance(data, context.user_id, context.is_dev_context)


@router.get("/opening-balances", response_model=list[OpeningBalanceRead])
async def list_opening_balances(session: Session, context: AccountRead, company_id: UUID | None = None, branch_id: UUID | None = None):
    service = CashBookService(session)
    return await service.list_opening_balances(_company(context, company_id), branch_id if context.is_dev_context else context.branch_id)


@router.post("/opening-balance", response_model=OpeningBalanceRead)
async def opening_balance_alias(data: OpeningBalanceCreate, session: Session, context: Annotated[RequestContext, Depends(require_permission("cashbook.opening_balance.manage", allow_any_company=True))]):
    return await CashBookService(session).set_opening_balance(data, context.user_id, context.is_dev_context)


@router.post("/accounts/{account_id}/opening-balance", response_model=OpeningBalanceRead)
async def account_opening_balance(account_id: UUID, data: OpeningBalanceCreate, session: Session, context: Annotated[RequestContext, Depends(require_permission("cashbook.opening_balance.manage", allow_any_company=True))]):
    if data.cash_account_id != account_id:
        raise HTTPException(status_code=422, detail="cash_account_id must match the account path.")
    return await CashBookService(session).set_opening_balance(data, context.user_id, context.is_dev_context)


@router.get("/transactions", response_model=list[CashTransactionRead])
async def list_transactions(
    session: Session, context: Read, company_id: UUID | None = None, branch_id: UUID | None = None,
    state: str | None = None, cash_account_id: UUID | None = None,
    start_date: date | None = None, end_date: date | None = None,
):
    return await CashBookService(session).list_transactions(_company(context, company_id), branch_id if context.is_dev_context else context.branch_id, state, cash_account_id, start_date, end_date)


@router.post("/transactions", response_model=CashTransactionRead, status_code=status.HTTP_201_CREATED)
async def create_transaction(data: CashTransactionCreate, session: Session, context: Create):
    return await CashBookService(session).create_transaction(data, context.user_id, context.is_dev_context)


@router.get("/transactions/{transaction_id}", response_model=CashTransactionRead)
async def get_transaction(transaction_id: UUID, session: Session, context: Read):
    service = CashBookService(session)
    item = await service.transaction(transaction_id)
    await service._allowed(context.user_id, "cashbook.transaction.view", item.company_id, item.branch_id, context.is_dev_context)
    return item


@router.get("/transactions/{transaction_id}/history")
async def transaction_history(transaction_id: UUID, session: Session, context: Read):
    service = CashBookService(session)
    item = await service.transaction(transaction_id)
    await service._allowed(context.user_id, "cashbook.transaction.view", item.company_id, item.branch_id, context.is_dev_context)
    rows = await service.history(transaction_id)
    return [{"id": row.id, "action": row.action, "user_id": row.user_id, "details": row.details, "created_at": row.created_at} for row in rows]


@router.patch("/transactions/{transaction_id}", response_model=CashTransactionRead)
async def update_transaction(transaction_id: UUID, data: CashTransactionUpdate, session: Session, context: Create):
    return await CashBookService(session).update_transaction(transaction_id, data.model_dump(exclude_unset=True), context.user_id, context.is_dev_context)


@router.post("/transactions/{transaction_id}/submit", response_model=CashTransactionRead)
async def submit_transaction(transaction_id: UUID, session: Session, context: Submit):
    return await CashBookService(session).submit(transaction_id, context.user_id, context.is_dev_context)


@router.post("/transactions/{transaction_id}/approve", response_model=CashTransactionRead)
async def approve_transaction(transaction_id: UUID, session: Session, context: Approve):
    return await CashBookService(session).approve(transaction_id, context.user_id, context.is_dev_context)


@router.post("/transactions/{transaction_id}/post", response_model=CashTransactionRead)
async def post_transaction(transaction_id: UUID, session: Session, context: Post):
    return await CashBookService(session).post(transaction_id, context.user_id, context.is_dev_context)


@router.post("/transactions/{transaction_id}/reject", response_model=CashTransactionRead)
async def reject_transaction(transaction_id: UUID, data: TransactionReject, session: Session, context: Reject):
    return await CashBookService(session).reject(transaction_id, data.reason, context.user_id, context.is_dev_context)


@router.post("/transactions/{transaction_id}/cancel", response_model=CashTransactionRead)
async def cancel_transaction(transaction_id: UUID, data: TransactionCancel, session: Session, context: Cancel):
    return await CashBookService(session).cancel(transaction_id, data.reason, context.user_id, context.is_dev_context)


@router.post("/transactions/{transaction_id}/reverse", response_model=CashTransactionRead, status_code=status.HTTP_201_CREATED)
async def reverse_transaction(transaction_id: UUID, session: Session, context: Reverse):
    return await CashBookService(session).reverse(transaction_id, context.user_id, context.is_dev_context)


@router.get("/daily-summary", response_model=list[DailySummaryRead])
async def daily_summary(
    session: Session, context: Summary, company_id: UUID | None = None, branch_id: UUID | None = None,
    summary_date: date | None = None,
):
    return await CashBookService(session).daily_summary(
        _company(context, company_id), branch_id if context.is_dev_context else context.branch_id,
        summary_date or datetime.now(UTC).date(),
    )
