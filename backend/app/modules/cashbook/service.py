import json
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import has_permission
from app.db.models import (
    AuditLog,
    CashAccount,
    CashDailySummary,
    CashOpeningBalance,
    CashTransaction,
)
from app.modules.cashbook.repository import CashBookRepository
from app.modules.cashbook.schemas import (
    CashAccountCreate,
    CashAccountUpdate,
    CashTransactionCreate,
    OpeningBalanceCreate,
)
from app.modules.notifications.events import APPROVAL_PENDING, PAYMENT_RECEIVED, DomainEvent
from app.modules.notifications.service import NotificationService


class CashBookService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repository = CashBookRepository(session)

    async def _allowed(self, actor_id: UUID, permission: str, company_id: UUID, branch_id: UUID | None, dev: bool) -> None:
        if not dev and not await has_permission(self.session, actor_id, permission, company_id, branch_id):
            raise HTTPException(status_code=403, detail="Permission denied.")

    async def _scope(self, company_id: UUID, branch_id: UUID | None) -> None:
        if await self.repository.company(company_id) is None:
            raise HTTPException(status_code=404, detail="Company not found.")
        if branch_id is not None and await self.repository.branch(company_id, branch_id) is None:
            raise HTTPException(status_code=404, detail="Branch not found for this company.")

    async def list_accounts(self, company_id: UUID, branch_id: UUID | None) -> list[CashAccount]:
        return await self.repository.list_accounts(company_id, branch_id)

    async def account_payload(self, account: CashAccount) -> dict:
        payload = {key: getattr(account, key) for key in (
            "id", "company_id", "branch_id", "account_id", "account_code", "name", "currency",
            "opening_balance", "is_active", "deleted_at", "created_at", "updated_at",
        )}
        payload["balance"] = account.opening_balance + await self.repository.posted_balance(account.id)
        return payload

    async def opening_amount(self, account: CashAccount, summary_date: date) -> Decimal:
        year = await self.repository.financial_year_for_date(account.company_id, summary_date)
        if year is None:
            return account.opening_balance
        opening = await self.repository.opening(account.id, year.id)
        return opening.amount if opening is not None else account.opening_balance

    async def account(self, account_id: UUID) -> CashAccount:
        account = await self.repository.account(account_id)
        if account is None:
            raise HTTPException(status_code=404, detail="Cash account not found.")
        return account

    async def create_account(self, data: CashAccountCreate, actor_id: UUID, dev: bool) -> CashAccount:
        await self._scope(data.company_id, data.branch_id)
        await self._allowed(actor_id, "cashbook.account.create", data.company_id, data.branch_id, dev)
        if data.account_id is not None:
            from app.db.models import Account
            account = await self.session.scalar(select(Account).where(Account.id == data.account_id, Account.company_id == data.company_id))
            if account is None or account.account_type_id is None:
                raise HTTPException(status_code=422, detail="Linked account does not belong to this company.")
        duplicate = await self.session.scalar(select(CashAccount.id).where(
            CashAccount.company_id == data.company_id, CashAccount.account_code == data.account_code,
            CashAccount.deleted_at.is_(None),
        ))
        if duplicate:
            raise HTTPException(status_code=409, detail="Cash account code already exists.")
        result = CashAccount(**data.model_dump())
        self.session.add(result)
        await self.session.flush()
        await self._audit(result, actor_id, "CASH_ACCOUNT_CREATED")
        await self.session.commit()
        await self.session.refresh(result)
        return result

    async def update_account(self, account_id: UUID, data: CashAccountUpdate, actor_id: UUID, dev: bool) -> CashAccount:
        account = await self.account(account_id)
        await self._allowed(actor_id, "cashbook.account.edit", account.company_id, account.branch_id, dev)
        if data.account_id is not None:
            from app.db.models import Account
            linked = await self.session.scalar(select(Account).where(Account.id == data.account_id, Account.company_id == account.company_id))
            if linked is None:
                raise HTTPException(status_code=422, detail="Linked account does not belong to this company.")
        for key, value in data.model_dump(exclude_unset=True).items():
            setattr(account, key, value)
        await self._audit(account, actor_id, "CASH_ACCOUNT_UPDATED", data.model_dump(exclude_unset=True))
        await self.session.commit()
        await self.session.refresh(account)
        return account

    async def set_opening_balance(self, data: OpeningBalanceCreate, actor_id: UUID, dev: bool) -> CashOpeningBalance:
        account = await self.account(data.cash_account_id)
        await self._allowed(actor_id, "cashbook.opening_balance.manage", account.company_id, account.branch_id, dev)
        year = await self.repository.financial_year(account.company_id, data.financial_year_id)
        if year is None:
            raise HTTPException(status_code=422, detail="Financial year does not belong to this company.")
        if not year.is_active or year.is_closed:
            raise HTTPException(status_code=422, detail="Financial year is not open.")
        existing = await self.repository.opening(account.id, year.id)
        if existing is None:
            existing = CashOpeningBalance(
                cash_account_id=account.id, company_id=account.company_id,
                financial_year_id=year.id, amount=data.amount, notes=data.notes, created_by=actor_id,
            )
            self.session.add(existing)
        else:
            existing.amount, existing.notes = data.amount, data.notes
        await self._audit(account, actor_id, "CASH_OPENING_BALANCE_SET", {"financial_year_id": str(year.id), "amount": str(data.amount)})
        await self.session.commit()
        await self.session.refresh(existing)
        return existing

    async def list_opening_balances(self, company_id: UUID, branch_id: UUID | None) -> list[CashOpeningBalance]:
        return await self.repository.list_openings(company_id, branch_id)

    async def create_transaction(self, data: CashTransactionCreate, actor_id: UUID, dev: bool) -> CashTransaction:
        await self._scope(data.company_id, data.branch_id)
        await self._allowed(actor_id, "cashbook.transaction.create", data.company_id, data.branch_id, dev)
        account = await self.repository.account(data.cash_account_id)
        if account is None or account.company_id != data.company_id or account.branch_id not in (None, data.branch_id):
            raise HTTPException(status_code=422, detail="Cash account is not valid for this company or branch.")
        if not account.is_active:
            raise HTTPException(status_code=422, detail="Cash account is inactive.")
        if data.target_cash_account_id:
            target = await self.repository.account(data.target_cash_account_id)
            if target is None or target.company_id != data.company_id or not target.is_active:
                raise HTTPException(status_code=422, detail="Target cash account is not valid.")
            if target.branch_id not in (None, data.branch_id):
                raise HTTPException(status_code=422, detail="Target cash account is not valid for this branch.")
        year = await self.repository.financial_year(data.company_id, data.financial_year_id)
        if year is None or not year.is_active or year.is_closed:
            raise HTTPException(status_code=422, detail="Financial year is not open for transactions.")
        if not year.contains(data.transaction_date):
            raise HTTPException(status_code=422, detail="Transaction date is outside the financial year.")
        result = CashTransaction(**data.model_dump(), created_by=actor_id)
        self.session.add(result)
        await self.session.flush()
        result.document_number = f"CB-{str(result.id).split('-')[0].upper()}"
        await self._audit(result, actor_id, "CASH_TRANSACTION_CREATED")
        await self.session.commit()
        await self.session.refresh(result)
        return result

    async def list_transactions(self, company_id: UUID, branch_id: UUID | None, state: str | None, account_id: UUID | None, start_date: date | None, end_date: date | None) -> list[CashTransaction]:
        return await self.repository.list_transactions(company_id, branch_id, state, account_id, start_date, end_date)

    async def transaction(self, transaction_id: UUID) -> CashTransaction:
        result = await self.repository.transaction(transaction_id)
        if result is None:
            raise HTTPException(status_code=404, detail="Cash transaction not found.")
        return result

    async def update_transaction(self, transaction_id: UUID, values: dict, actor_id: UUID, dev: bool) -> CashTransaction:
        item = await self.repository.transaction(transaction_id, lock=True)
        if item is None:
            raise HTTPException(status_code=404, detail="Cash transaction not found.")
        await self._allowed(actor_id, "cashbook.transaction.create", item.company_id, item.branch_id, dev)
        if item.state not in {"DRAFT", "REJECTED"}:
            raise HTTPException(status_code=409, detail="Only draft or rejected transactions can be edited.")
        if "transaction_date" in values:
            year = await self.repository.financial_year(item.company_id, item.financial_year_id)
            if year is None or not year.contains(values["transaction_date"]):
                raise HTTPException(status_code=422, detail="Transaction date is outside the financial year.")
        for key, value in values.items():
            setattr(item, key, value)
        await self._audit(item, actor_id, "CASH_TRANSACTION_UPDATED", values)
        await self.session.commit()
        await self.session.refresh(item)
        return item

    async def _transition(self, transaction_id: UUID, target: str, actor_id: UUID, dev: bool, reason: str | None = None) -> CashTransaction:
        item = await self.repository.transaction(transaction_id, lock=True)
        if item is None:
            raise HTTPException(status_code=404, detail="Cash transaction not found.")
        permissions = {
            "SUBMITTED": "cashbook.transaction.submit", "APPROVED": "cashbook.transaction.approve",
            "POSTED": "cashbook.transaction.post", "REJECTED": "cashbook.transaction.reject",
            "CANCELLED": "cashbook.transaction.cancel",
        }
        await self._allowed(actor_id, permissions[target], item.company_id, item.branch_id, dev)
        allowed = {
            "SUBMITTED": {"DRAFT", "REJECTED"}, "APPROVED": {"SUBMITTED"},
            "POSTED": {"APPROVED"}, "REJECTED": {"SUBMITTED"}, "CANCELLED": {"DRAFT", "SUBMITTED", "APPROVED"},
        }
        if item.state not in allowed[target]:
            raise HTTPException(status_code=409, detail=f"Transaction cannot move from {item.state} to {target}.")
        now = datetime.now(UTC)
        item.state = target
        if target == "SUBMITTED":
            item.submitted_by, item.submitted_at = actor_id, now
        elif target == "APPROVED":
            item.approved_by, item.approved_at = actor_id, now
        elif target == "POSTED":
            await self._post_locked(item, actor_id, now)
        elif target == "REJECTED":
            item.rejection_reason = reason
        elif target == "CANCELLED":
            item.cancellation_reason, item.cancelled_at = reason, now
        await self._audit(item, actor_id, f"CASH_TRANSACTION_{target}", {"reason": reason} if reason else None)
        if target == "POSTED" and item.transaction_type == "receipt":
            await NotificationService(self.session).publish(
                DomainEvent(
                    event_type=PAYMENT_RECEIVED,
                    subject_id=item.id,
                    user_id=actor_id,
                    company_id=item.company_id,
                    branch_id=item.branch_id,
                    payload={"cash_transaction_id": str(item.id), "amount": str(item.amount)},
                ),
                recipients={actor_id},
            )
        elif target == "SUBMITTED":
            await NotificationService(self.session).publish(
                DomainEvent(
                    event_type=APPROVAL_PENDING,
                    subject_id=item.id,
                    user_id=actor_id,
                    company_id=item.company_id,
                    branch_id=item.branch_id,
                    payload={"cash_transaction_id": str(item.id)},
                ),
                recipients={actor_id},
            )
        await self.session.commit()
        await self.session.refresh(item)
        return item

    async def submit(self, transaction_id: UUID, actor_id: UUID, dev: bool) -> CashTransaction:
        return await self._transition(transaction_id, "SUBMITTED", actor_id, dev)

    async def approve(self, transaction_id: UUID, actor_id: UUID, dev: bool) -> CashTransaction:
        return await self._transition(transaction_id, "APPROVED", actor_id, dev)

    async def post(self, transaction_id: UUID, actor_id: UUID, dev: bool) -> CashTransaction:
        return await self._transition(transaction_id, "POSTED", actor_id, dev)

    async def reject(self, transaction_id: UUID, reason: str, actor_id: UUID, dev: bool) -> CashTransaction:
        return await self._transition(transaction_id, "REJECTED", actor_id, dev, reason)

    async def cancel(self, transaction_id: UUID, reason: str, actor_id: UUID, dev: bool) -> CashTransaction:
        return await self._transition(transaction_id, "CANCELLED", actor_id, dev, reason)

    async def _post_locked(self, item: CashTransaction, actor_id: UUID, now: datetime) -> None:
        # Lock both ledger rows in a stable order to prevent transfer deadlocks.
        ids = sorted([item.cash_account_id] + ([item.target_cash_account_id] if item.target_cash_account_id else []), key=str)
        for account_id in ids:
            if await self.repository.account(account_id, lock=True) is None:
                raise HTTPException(status_code=422, detail="Cash account no longer exists.")
        item.posted_by, item.posted_at = actor_id, now
        await self.session.flush()
        for account_id in ids:
            account = await self.repository.account(account_id)
            if account:
                await self._refresh_daily(account, item.transaction_date)

    async def reverse(self, transaction_id: UUID, actor_id: UUID, dev: bool) -> CashTransaction:
        original = await self.repository.transaction(transaction_id, lock=True)
        if original is None:
            raise HTTPException(status_code=404, detail="Cash transaction not found.")
        await self._allowed(actor_id, "cashbook.transaction.reverse", original.company_id, original.branch_id, dev)
        if original.state != "POSTED":
            raise HTTPException(status_code=409, detail="Only posted transactions can be reversed.")
        existing = await self.session.scalar(select(CashTransaction.id).where(CashTransaction.reversal_of_id == original.id))
        if existing:
            raise HTTPException(status_code=409, detail="Transaction has already been reversed.")
        reversal_type = {"receipt": "payment", "payment": "receipt", "transfer": "transfer"}[original.transaction_type]
        reversal = CashTransaction(
            company_id=original.company_id, branch_id=original.branch_id,
            cash_account_id=original.target_cash_account_id if reversal_type == "transfer" else original.cash_account_id,
            target_cash_account_id=original.cash_account_id if reversal_type == "transfer" else None,
            financial_year_id=original.financial_year_id, transaction_type=reversal_type,
            transaction_date=original.transaction_date, amount=original.amount,
            reference=f"Reversal of {original.document_number}", description=f"Reversal of {original.description or original.document_number}",
            state="POSTED", reversal_of_id=original.id, created_by=actor_id, posted_by=actor_id,
            submitted_by=actor_id, approved_by=actor_id, submitted_at=datetime.now(UTC),
            approved_at=datetime.now(UTC), posted_at=datetime.now(UTC),
        )
        self.session.add(reversal)
        await self.session.flush()
        reversal.document_number = f"CB-R-{str(reversal.id).split('-')[0].upper()}"
        original.reversed_by, original.reversed_at = actor_id, datetime.now(UTC)
        for account_id in {reversal.cash_account_id, reversal.target_cash_account_id} - {None}:
            account = await self.repository.account(account_id, lock=True)
            if account:
                await self._refresh_daily(account, reversal.transaction_date)
        await self._audit(original, actor_id, "CASH_TRANSACTION_REVERSED", {"reversal_id": str(reversal.id)})
        await self.session.commit()
        await self.session.refresh(reversal)
        return reversal

    async def _refresh_daily(self, account: CashAccount, summary_date: date) -> None:
        rows = await self.repository.posted_for_day(account.company_id, account.branch_id, account.id, summary_date)
        receipts = payments = transfers_in = transfers_out = Decimal(0)
        for row in rows:
            if row.transaction_type == "receipt":
                receipts += row.amount
            elif row.transaction_type == "payment":
                payments += row.amount
            elif row.cash_account_id == account.id:
                transfers_out += row.amount
            else:
                transfers_in += row.amount
        opening = await self.opening_amount(account, summary_date)
        balance = opening + await self.repository.posted_balance(account.id, summary_date)
        summary = await self.session.scalar(select(CashDailySummary).where(
            CashDailySummary.company_id == account.company_id, CashDailySummary.branch_id == account.branch_id,
            CashDailySummary.cash_account_id == account.id, CashDailySummary.summary_date == summary_date,
        ))
        if summary is None:
            summary = CashDailySummary(company_id=account.company_id, branch_id=account.branch_id, cash_account_id=account.id, summary_date=summary_date)
            self.session.add(summary)
        summary.receipts, summary.payments, summary.transfers_in = receipts, payments, transfers_in
        summary.transfers_out, summary.closing_balance = transfers_out, balance

    async def daily_summary(self, company_id: UUID, branch_id: UUID | None, summary_date: date) -> list[dict]:
        accounts = await self.repository.list_accounts(company_id, branch_id)
        output = []
        for account in accounts:
            rows = await self.repository.posted_for_day(company_id, branch_id, account.id, summary_date)
            receipts = sum((r.amount for r in rows if r.transaction_type == "receipt"), Decimal(0))
            payments = sum((r.amount for r in rows if r.transaction_type == "payment"), Decimal(0))
            incoming = sum((r.amount for r in rows if r.transaction_type == "transfer" and r.target_cash_account_id == account.id), Decimal(0))
            outgoing = sum((r.amount for r in rows if r.transaction_type == "transfer" and r.cash_account_id == account.id), Decimal(0))
            opening = await self.opening_amount(account, summary_date)
            output.append({"summary_date": summary_date, "cash_account_id": account.id, "cash_account_name": account.name,
                           "opening_balance": opening, "receipts": receipts, "payments": payments,
                           "transfers_in": incoming, "transfers_out": outgoing,
                           "closing_balance": opening + await self.repository.posted_balance(account.id, summary_date)})
        return output

    async def history(self, transaction_id: UUID) -> list[AuditLog]:
        await self.transaction(transaction_id)
        return list(await self.session.scalars(select(AuditLog).where(
            AuditLog.entity_type == "cash_transaction", AuditLog.entity_id == transaction_id,
        ).order_by(AuditLog.created_at)))

    async def _audit(self, entity: CashAccount | CashTransaction, actor_id: UUID, action: str, details: dict | None = None) -> None:
        self.session.add(AuditLog(
            company_id=entity.company_id, branch_id=entity.branch_id, user_id=actor_id,
            action=action, entity_type="cash_account" if isinstance(entity, CashAccount) else "cash_transaction",
            entity_id=entity.id, details=json.dumps(details or {}, default=str),
        ))
