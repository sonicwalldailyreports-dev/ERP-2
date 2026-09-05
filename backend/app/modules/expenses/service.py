from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import has_permission
from app.db.models import AuditLog, CashTransaction, Expense, ExpenseCategory
from app.modules.cashbook.service import CashBookService
from app.modules.expenses.repository import ExpenseRepository
from app.modules.expenses.schemas import ExpenseCorrection, ExpenseCreate, ExpenseUpdate
from app.modules.notifications.events import (
    APPROVAL_PENDING,
    EXPENSE_APPROVED,
    EXPENSE_REJECTED,
    EXPENSE_SUBMITTED,
    PAYMENT_RECEIVED,
    DomainEvent,
)
from app.modules.notifications.service import NotificationService


class ExpenseService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repository = ExpenseRepository(session)

    async def _allowed(
        self, actor_id: UUID, permission: str, company_id: UUID, branch_id: UUID | None, dev: bool
    ) -> None:
        if not dev and not await has_permission(
            self.session, actor_id, permission, company_id, branch_id
        ):
            raise HTTPException(status_code=403, detail="Permission denied.")

    async def _scope(self, company_id: UUID, branch_id: UUID | None) -> None:
        if await self.repository.company(company_id) is None:
            raise HTTPException(status_code=404, detail="Company not found.")
        if branch_id is not None and await self.repository.branch(company_id, branch_id) is None:
            raise HTTPException(status_code=404, detail="Branch not found for this company.")

    async def _validate_references(
        self, data: ExpenseCreate | ExpenseUpdate, company_id: UUID, branch_id: UUID | None
    ) -> None:
        values = data.model_dump(exclude_unset=True)
        category_id = values.get("category_id")
        if category_id is not None and await self.repository.category(category_id, company_id, branch_id) is None:
            raise HTTPException(status_code=422, detail="Category is not valid for this company or branch.")
        account_id = values.get("account_id")
        if account_id is not None:
            account = await self.repository.account(account_id, company_id)
            if account is None or account.branch_id not in (None, branch_id):
                raise HTTPException(status_code=422, detail="Expense account is not valid.")
        cash_id = values.get("cash_account_id")
        payment_method = values.get("payment_method")
        if payment_method is not None and payment_method not in ("cash", "bank", "card", "credit", "other"):
            raise HTTPException(status_code=422, detail="Unsupported payment method.")
        if payment_method in ("cash", "bank", "card") and cash_id is None:
            raise HTTPException(status_code=422, detail="cash_account_id is required for this payment method.")
        if cash_id is not None:
            cash = await self.repository.cash_account(cash_id, company_id)
            if cash is None or cash.branch_id not in (None, branch_id):
                raise HTTPException(status_code=422, detail="Cash account is not valid for this company or branch.")

    async def _validate_year(self, company_id: UUID, year_id: UUID, expense_date) -> None:
        year = await self.repository.financial_year(company_id, year_id)
        if year is None or not year.is_active or year.is_closed:
            raise HTTPException(status_code=422, detail="Financial year is not open for expenses.")
        if not year.contains(expense_date):
            raise HTTPException(status_code=422, detail="Expense date is outside the financial year.")

    async def list_categories(self, company_id: UUID, branch_id: UUID | None) -> list[ExpenseCategory]:
        return await self.repository.list_categories(company_id, branch_id)

    async def create_category(
        self, data, actor_id: UUID, dev: bool
    ) -> ExpenseCategory:
        await self._scope(data.company_id, data.branch_id)
        await self._allowed(actor_id, "expenses.category.create", data.company_id, data.branch_id, dev)
        if await self.repository.category_by_code(data.company_id, data.code):
            raise HTTPException(status_code=409, detail="Category code already exists.")
        result = ExpenseCategory(**data.model_dump())
        self.session.add(result)
        await self.session.flush()
        await self._audit(result, actor_id, "EXPENSE_CATEGORY_CREATED")
        await self.session.commit()
        await self.session.refresh(result)
        return result

    async def update_category(self, category_id: UUID, data, actor_id: UUID, dev: bool) -> ExpenseCategory:
        result = await self.session.scalar(select(ExpenseCategory).where(ExpenseCategory.id == category_id))
        if result is None:
            raise HTTPException(status_code=404, detail="Expense category not found.")
        await self._allowed(actor_id, "expenses.category.edit", result.company_id, result.branch_id, dev)
        values = data.model_dump(exclude_unset=True)
        if "code" in values and values["code"] != result.code and await self.repository.category_by_code(result.company_id, values["code"]):
            raise HTTPException(status_code=409, detail="Category code already exists.")
        for key, value in values.items():
            setattr(result, key, value.strip().upper() if key == "code" else value)
        await self._audit(result, actor_id, "EXPENSE_CATEGORY_UPDATED", values)
        await self.session.commit()
        await self.session.refresh(result)
        return result

    async def create(self, data: ExpenseCreate, actor_id: UUID, dev: bool) -> Expense:
        await self._scope(data.company_id, data.branch_id)
        await self._allowed(actor_id, "expenses.expense.create", data.company_id, data.branch_id, dev)
        await self._validate_year(data.company_id, data.financial_year_id, data.date)
        await self._validate_references(data, data.company_id, data.branch_id)
        values = data.model_dump()
        values["expense_number"] = values.get("expense_number") or f"EXP-{uuid4().hex[:12].upper()}"
        result = Expense(**values, created_by=actor_id)
        self.session.add(result)
        await self.session.flush()
        await self._audit(result, actor_id, "EXPENSE_CREATED")
        await self.session.commit()
        await self.session.refresh(result)
        return result

    async def get(self, expense_id: UUID, actor_id: UUID, dev: bool, permission: str = "expenses.expense.view") -> Expense:
        result = await self.repository.expense(expense_id)
        if result is None:
            raise HTTPException(status_code=404, detail="Expense not found.")
        await self._allowed(actor_id, permission, result.company_id, result.branch_id, dev)
        return result

    async def list(
        self, company_id: UUID, branch_id: UUID | None, status: str | None, category_id: UUID | None,
        start_date, end_date, search: str | None, actor_id: UUID, dev: bool,
    ) -> list[Expense]:
        await self._scope(company_id, branch_id)
        await self._allowed(actor_id, "expenses.expense.view", company_id, branch_id, dev)
        return await self.repository.list_expenses(
            company_id, branch_id, status, category_id, start_date, end_date, search
        )

    async def update(self, expense_id: UUID, data: ExpenseUpdate, actor_id: UUID, dev: bool) -> Expense:
        result = await self.get(expense_id, actor_id, dev, "expenses.expense.edit")
        if result.status not in ("DRAFT", "REJECTED"):
            raise HTTPException(status_code=409, detail="Only draft or rejected expenses can be edited.")
        values = data.model_dump(exclude_unset=True)
        company_id, branch_id = result.company_id, result.branch_id
        if "financial_year_id" in values or "date" in values:
            await self._validate_year(
                company_id, values.get("financial_year_id", result.financial_year_id),
                values.get("date", result.date),
            )
        await self._validate_references(data, company_id, branch_id)
        payment_method = values.get("payment_method", result.payment_method)
        cash_account_id = values.get("cash_account_id", result.cash_account_id)
        if payment_method in ("cash", "bank", "card") and cash_account_id is None:
            raise HTTPException(status_code=422, detail="cash_account_id is required for this payment method.")
        for key, value in values.items():
            setattr(result, key, value)
        await self._audit(result, actor_id, "EXPENSE_UPDATED", values)
        await self.session.commit()
        await self.session.refresh(result)
        return result

    async def _cash_entry(self, expense: Expense, actor_id: UUID, transaction_type: str) -> None:
        if expense.cash_account_id is None:
            return
        amount = expense.amount + expense.tax_amount
        now = datetime.now(UTC)
        entry = CashTransaction(
            company_id=expense.company_id,
            branch_id=expense.branch_id,
            cash_account_id=expense.cash_account_id,
            financial_year_id=expense.financial_year_id,
            transaction_type=transaction_type,
            transaction_date=expense.date,
            amount=amount,
            reference=expense.reference or expense.expense_number,
            description=expense.description,
            document_number=f"CB-EXP-{str(expense.id).split('-')[0].upper()}",
            state="POSTED",
            created_by=actor_id,
            submitted_by=actor_id,
            approved_by=actor_id,
            posted_by=actor_id,
            submitted_at=now,
            approved_at=now,
            posted_at=now,
            source_expense_id=expense.id,
        )
        self.session.add(entry)
        await self.session.flush()
        account = await self.repository.cash_account(expense.cash_account_id, expense.company_id)
        if account:
            await CashBookService(self.session)._refresh_daily(account, expense.date)

    async def transition(self, expense_id: UUID, target: str, actor_id: UUID, dev: bool, reason: str | None = None) -> Expense:
        result = await self.repository.expense(expense_id, lock=True)
        if result is None:
            raise HTTPException(status_code=404, detail="Expense not found.")
        permissions = {
            "SUBMITTED": "expenses.expense.submit",
            "APPROVED": "expenses.expense.approve",
            "POSTED": "expenses.expense.post",
            "REJECTED": "expenses.expense.reject",
            "CANCELLED": "expenses.expense.cancel",
        }
        await self._allowed(actor_id, permissions[target], result.company_id, result.branch_id, dev)
        allowed = {
            "SUBMITTED": {"DRAFT", "REJECTED"},
            "APPROVED": {"SUBMITTED"},
            "POSTED": {"APPROVED"},
            "REJECTED": {"SUBMITTED"},
            "CANCELLED": {"DRAFT", "SUBMITTED", "APPROVED"},
        }
        if result.status not in allowed[target]:
            raise HTTPException(status_code=409, detail=f"Expense cannot move from {result.status} to {target}.")
        if target == "POSTED":
            await self._validate_year(result.company_id, result.financial_year_id, result.date)
            await self._validate_references(
                ExpenseUpdate(
                    category_id=result.category_id, account_id=result.account_id,
                    payment_method=result.payment_method, cash_account_id=result.cash_account_id,
                ),
                result.company_id,
                result.branch_id,
            )
        now = datetime.now(UTC)
        result.status = target
        if target == "SUBMITTED":
            result.rejection_reason = None
        elif target == "APPROVED":
            result.approved_by, result.approved_at = actor_id, now
        elif target == "POSTED":
            result.posted_by, result.posted_at = actor_id, now
            await self.session.flush()
            await self._cash_entry(result, actor_id, "payment")
        elif target == "REJECTED":
            result.rejection_reason = reason
        elif target == "CANCELLED":
            result.cancellation_reason = reason
        await self._audit(result, actor_id, f"EXPENSE_{target}", {"reason": reason} if reason else {})
        event_type = {
            "SUBMITTED": EXPENSE_SUBMITTED,
            "APPROVED": EXPENSE_APPROVED,
            "REJECTED": EXPENSE_REJECTED,
            "POSTED": PAYMENT_RECEIVED,
        }.get(target)
        if event_type:
            recipients = {actor_id}
            if result.created_by:
                recipients.add(result.created_by)
            await NotificationService(self.session).publish(
                DomainEvent(
                    event_type=event_type,
                    subject_id=result.id,
                    user_id=actor_id,
                    company_id=result.company_id,
                    branch_id=result.branch_id,
                    payload={"expense_id": str(result.id), "status": target},
                ),
                recipients=recipients,
            )
        if target == "SUBMITTED":
            await NotificationService(self.session).publish(
                DomainEvent(
                    event_type=APPROVAL_PENDING,
                    subject_id=result.id,
                    user_id=actor_id,
                    company_id=result.company_id,
                    branch_id=result.branch_id,
                    payload={"expense_id": str(result.id)},
                ),
                recipients={actor_id},
            )
        await self.session.commit()
        await self.session.refresh(result)
        return result

    async def reverse(self, expense_id: UUID, actor_id: UUID, dev: bool) -> Expense:
        original = await self.get(expense_id, actor_id, dev, "expenses.expense.reverse")
        if original.status != "POSTED":
            raise HTTPException(status_code=409, detail="Only posted expenses can be reversed.")
        existing = await self.session.scalar(
            select(Expense.id).where(Expense.reversal_of_id == original.id)
        )
        if existing:
            raise HTTPException(status_code=409, detail="Expense has already been reversed.")
        now = datetime.now(UTC)
        reversal = Expense(
            company_id=original.company_id, branch_id=original.branch_id,
            financial_year_id=original.financial_year_id,
            expense_number=f"EXP-R-{str(original.id).split('-')[0].upper()}",
            date=original.date, category_id=original.category_id, account_id=original.account_id,
            description=f"Reversal of {original.description or original.expense_number}",
            vendor=original.vendor, amount=original.amount, tax_amount=original.tax_amount,
            payment_method=original.payment_method, cash_account_id=original.cash_account_id,
            reference=f"Reversal of {original.expense_number}", attachment=original.attachment,
            status="POSTED", created_by=actor_id, approved_by=actor_id, posted_by=actor_id,
            approved_at=now, posted_at=now, reversal_of_id=original.id,
        )
        self.session.add(reversal)
        original.reversed_by, original.reversed_at = actor_id, now
        await self.session.flush()
        await self._cash_entry(reversal, actor_id, "receipt")
        await self._audit(original, actor_id, "EXPENSE_REVERSED", {"reversal_id": str(reversal.id)})
        await self.session.commit()
        await self.session.refresh(reversal)
        return reversal

    async def correct(self, expense_id: UUID, data: ExpenseCorrection, actor_id: UUID, dev: bool) -> Expense:
        original = await self.get(expense_id, actor_id, dev, "expenses.expense.adjust")
        if original.status != "POSTED":
            raise HTTPException(status_code=409, detail="Only posted expenses can be corrected.")
        values = {
            "company_id": original.company_id, "branch_id": original.branch_id,
            "financial_year_id": original.financial_year_id,
            "expense_number": f"EXP-A-{str(original.id).split('-')[0].upper()}",
            "date": original.date, "category_id": original.category_id, "account_id": original.account_id,
            "description": f"Adjustment of {original.expense_number}: {data.reason}",
            "vendor": original.vendor, "amount": data.amount or original.amount,
            "tax_amount": original.tax_amount, "payment_method": original.payment_method,
            "cash_account_id": original.cash_account_id, "reference": original.reference,
            "attachment": original.attachment, "status": "DRAFT", "created_by": actor_id,
            "correction_of_id": original.id,
        }
        result = Expense(**values)
        self.session.add(result)
        await self.session.flush()
        await self._audit(result, actor_id, "EXPENSE_ADJUSTMENT_CREATED", {"reason": data.reason})
        await self.session.commit()
        await self.session.refresh(result)
        return result

    async def history(self, expense_id: UUID, actor_id: UUID, dev: bool) -> list[AuditLog]:
        await self.get(expense_id, actor_id, dev)
        return list(await self.session.scalars(
            select(AuditLog).where(
                AuditLog.entity_type.in_(("expense", "expense_category")),
                AuditLog.entity_id == expense_id,
            ).order_by(AuditLog.created_at)
        ))

    async def _audit(self, entity, actor_id: UUID, action: str, details: dict | None = None) -> None:
        self.session.add(
            AuditLog(
                company_id=entity.company_id,
                branch_id=entity.branch_id,
                user_id=actor_id,
                action=action,
                entity_type="expense_category" if isinstance(entity, ExpenseCategory) else "expense",
                entity_id=entity.id,
                details=json.dumps(details or {}, default=str),
            )
        )
