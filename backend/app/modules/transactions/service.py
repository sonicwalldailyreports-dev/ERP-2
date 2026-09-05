"""Framework-independent double-entry transaction application service."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import has_permission
from app.db.models import AuditLog, Transaction, TransactionLine
from app.modules.numbering.repository import NumberSequenceRepository
from app.modules.transactions.repository import FinancialTransactionRepository
from app.modules.transactions.schemas import TransactionCreate

ZERO = Decimal("0.00")


class FinancialTransactionError(ValueError):
    """Base exception raised by the financial transaction engine."""


class TransactionValidationError(FinancialTransactionError):
    pass


class TransactionNotFoundError(FinancialTransactionError):
    pass


class TransactionAuthorizationError(FinancialTransactionError):
    pass


class DuplicateTransactionNumberError(FinancialTransactionError):
    pass


class TransactionStateError(FinancialTransactionError):
    pass


class TransactionImmutabilityError(FinancialTransactionError):
    pass


class FinancialTransactionService:
    """Posts balanced transactions without depending on FastAPI or HTTP errors.

    The service owns the database transaction for each public operation.  A
    caller can therefore use it from an API route, a worker, or a scheduled
    task without importing any web framework.
    """

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repository = FinancialTransactionRepository(session)
        self.numbering = NumberSequenceRepository(session)

    async def create(
        self,
        data: TransactionCreate | dict[str, Any] | None = None,
        actor_id: UUID | None = None,
        is_dev_context: bool | None = None,
        **values: Any,
    ) -> Transaction:
        payload = self._payload(data, values)
        request = TransactionCreate.model_validate(payload)
        await self._authorize(
            actor_id,
            request.company_id,
            request.branch_id,
            "transactions.transaction.create",
            is_dev_context,
        )
        await self._validate_scope(request)
        await self._validate_lines(request.company_id, request.branch_id, request.lines)
        self._validate_balance(request.lines)

        number = await self._number(
            request.company_id,
            request.branch_id,
            request.financial_year_id,
            request.transaction_number,
        )
        if await self.repository.existing_number(request.company_id, number):
            raise DuplicateTransactionNumberError(
                f"Transaction number {number!r} already exists for this company."
            )
        transaction = Transaction(
            company_id=request.company_id,
            branch_id=request.branch_id,
            financial_year_id=request.financial_year_id,
            transaction_number=number,
            transaction_date=request.transaction_date,
            reference=request.reference,
            source_module=request.source_module,
            source_document=self._string(request.source_document),
            description=request.description,
            status="DRAFT",
            created_by=actor_id,
        )
        transaction.lines = [
            TransactionLine(
                company_id=request.company_id,
                account_id=line.account_id,
                line_number=index,
                description=line.description,
                debit=self._money(line.debit),
                credit=self._money(line.credit),
            )
            for index, line in enumerate(request.lines, 1)
        ]
        self.session.add(transaction)
        try:
            await self.session.flush()
            self._audit(
                transaction,
                actor_id,
                "TRANSACTION_CREATED",
                {"transaction_number": transaction.transaction_number},
            )
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            if "number" in str(exc).lower() or "transaction" in str(exc).lower():
                raise DuplicateTransactionNumberError(
                    f"Transaction number {number!r} already exists for this company."
                ) from None
            raise
        await self.session.refresh(transaction)
        await self.session.refresh(transaction, attribute_names=["lines"])
        return transaction

    async def create_transaction(
        self,
        data: TransactionCreate | dict[str, Any] | None = None,
        actor_id: UUID | None = None,
        is_dev_context: bool | None = None,
        **values: Any,
    ) -> Transaction:
        return await self.create(data, actor_id, is_dev_context, **values)

    async def get(
        self,
        transaction_id: UUID,
        actor_id: UUID | None = None,
        *,
        permission_code: str = "transactions.transaction.view",
        is_dev_context: bool | None = None,
    ) -> Transaction:
        transaction = await self.repository.get(transaction_id)
        if transaction is None:
            raise TransactionNotFoundError(f"Transaction {transaction_id} was not found.")
        await self._authorize(
            actor_id,
            transaction.company_id,
            transaction.branch_id,
            permission_code,
            is_dev_context,
        )
        return transaction

    async def list(
        self,
        company_id: UUID,
        branch_id: UUID | None = None,
        status: str | None = None,
        start_date=None,
        end_date=None,
    ) -> list[Transaction]:
        return await self.repository.list(company_id, branch_id, status, start_date, end_date)

    async def post(
        self, transaction_id: UUID, actor_id: UUID | None = None, is_dev_context: bool | None = None
    ) -> Transaction:
        transaction = await self.repository.get(transaction_id, lock=True)
        if transaction is None:
            raise TransactionNotFoundError(f"Transaction {transaction_id} was not found.")
        await self._authorize(
            actor_id,
            transaction.company_id,
            transaction.branch_id,
            "transactions.transaction.post",
            is_dev_context,
        )
        if transaction.status != "DRAFT":
            raise TransactionStateError(
                f"Only draft transactions can be posted (current state: {transaction.status})."
            )
        await self._validate_scope(
            TransactionCreate(
                company_id=transaction.company_id,
                branch_id=transaction.branch_id,
                financial_year_id=transaction.financial_year_id,
                transaction_date=transaction.transaction_date,
                lines=[
                    {
                        "account_id": line.account_id,
                        "debit": line.debit,
                        "credit": line.credit,
                    }
                    for line in transaction.lines
                ],
            )
        )
        await self._validate_lines(
            transaction.company_id,
            transaction.branch_id,
            [
                {
                    "account_id": line.account_id,
                    "debit": line.debit,
                    "credit": line.credit,
                }
                for line in transaction.lines
            ],
        )
        self._validate_balance(transaction.lines)
        now = datetime.now(UTC)
        transaction.status = "POSTED"
        transaction.posted_by = actor_id
        transaction.posted_at = now
        self._audit(transaction, actor_id, "TRANSACTION_POSTED")
        try:
            await self.session.commit()
        except IntegrityError:
            await self.session.rollback()
            raise
        await self.session.refresh(transaction)
        await self.session.refresh(transaction, attribute_names=["lines"])
        return transaction

    async def post_transaction(
        self, transaction_id: UUID,         actor_id: UUID | None = None,
        is_dev_context: bool | None = None,
    ) -> Transaction:
        return await self.post(transaction_id, actor_id, is_dev_context)

    async def reverse(
        self,
        transaction_id: UUID,
        actor_id: UUID | None = None,
        reference: str | None = None,
        description: str | None = None,
        *,
        is_dev_context: bool | None = None,
    ) -> Transaction:
        original = await self.repository.get(transaction_id, lock=True)
        if original is None:
            raise TransactionNotFoundError(f"Transaction {transaction_id} was not found.")
        await self._authorize(
            actor_id,
            original.company_id,
            original.branch_id,
            "transactions.transaction.reverse",
            is_dev_context,
        )
        if original.status != "POSTED":
            raise TransactionStateError("Only posted transactions can be reversed.")
        if await self.repository.reversal(original.id):
            raise TransactionStateError("Transaction has already been reversed.")
        await self._validate_year(
            original.company_id, original.financial_year_id, original.transaction_date
        )
        number = await self._number(
            original.company_id,
            original.branch_id,
            original.financial_year_id,
            None,
        )
        if await self.repository.existing_number(original.company_id, number):
            raise DuplicateTransactionNumberError(
                f"Transaction number {number!r} already exists for this company."
            )
        reversal = Transaction(
            company_id=original.company_id,
            branch_id=original.branch_id,
            financial_year_id=original.financial_year_id,
            transaction_number=number,
            transaction_date=original.transaction_date,
            reference=reference or f"Reversal of {original.transaction_number}",
            source_module="transactions",
            source_document=str(original.id),
            description=description or f"Reversal of {original.description or original.transaction_number}",
            status="POSTED",
            created_by=actor_id,
            posted_by=actor_id,
            posted_at=datetime.now(UTC),
            reversal_of_id=original.id,
        )
        reversal.lines = [
            TransactionLine(
                company_id=original.company_id,
                account_id=line.account_id,
                line_number=line.line_number,
                description=line.description,
                debit=self._money(line.credit),
                credit=self._money(line.debit),
            )
            for line in original.lines
        ]
        original.status = "REVERSED"
        original.reversed_by = actor_id
        original.reversed_at = datetime.now(UTC)
        self.session.add(reversal)
        try:
            await self.session.flush()
            self._audit(
                original,
                actor_id,
                "TRANSACTION_REVERSED",
                {"reversal_id": str(reversal.id)},
            )
            self._audit(
                reversal,
                actor_id,
                "TRANSACTION_CREATED",
                {"reversal_of_id": str(original.id)},
            )
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            if "reversal" in str(exc).lower() or "number" in str(exc).lower():
                raise TransactionStateError("Transaction has already been reversed.") from None
            raise
        await self.session.refresh(reversal)
        await self.session.refresh(reversal, attribute_names=["lines"])
        return reversal

    async def reverse_transaction(
        self,
        transaction_id: UUID,
        actor_id: UUID | None = None,
        **kwargs: Any,
    ) -> Transaction:
        return await self.reverse(transaction_id, actor_id, **kwargs)

    async def update(self, transaction_id: UUID, **_: Any) -> Transaction:
        transaction = await self.get(transaction_id)
        raise TransactionImmutabilityError(
            f"Transactions are immutable; {transaction.transaction_number} cannot be edited."
        )

    async def delete(self, transaction_id: UUID) -> None:
        transaction = await self.get(transaction_id)
        raise TransactionImmutabilityError(
            f"Transactions are immutable; {transaction.transaction_number} cannot be deleted."
        )

    async def _validate_scope(self, request: TransactionCreate) -> None:
        if await self.repository.company(request.company_id) is None:
            raise TransactionValidationError("Company does not exist or is inactive.")
        if request.branch_id is not None and await self.repository.branch(
            request.company_id, request.branch_id
        ) is None:
            raise TransactionValidationError("Branch does not belong to the company.")
        await self._validate_year(
            request.company_id, request.financial_year_id, request.transaction_date
        )

    async def _validate_year(self, company_id: UUID, year_id: UUID, value) -> None:
        year = await self.repository.financial_year(company_id, year_id)
        if year is None:
            raise TransactionValidationError("Financial year does not belong to the company.")
        if not year.is_active or year.is_closed:
            raise TransactionValidationError("Financial year is not open.")
        if not year.contains(value):
            raise TransactionValidationError("Transaction date is outside the financial year.")

    async def _authorize(
        self,
        actor_id: UUID | None,
        company_id: UUID,
        branch_id: UUID | None,
        permission_code: str,
        is_dev_context: bool | None = None,
    ) -> None:
        # ``None`` retains the legacy unauthenticated service API used by
        # isolated tests and local integrations.  API routes always pass an
        # explicit context, so an omitted actor cannot bypass production auth.
        if is_dev_context is None:
            return
        if is_dev_context:
            return
        if actor_id is None:
            raise TransactionAuthorizationError("Transaction scope or permission is not allowed.")
        if not await has_permission(
            self.session, actor_id, permission_code, company_id, branch_id
        ):
            raise TransactionAuthorizationError("Transaction scope or permission is not allowed.")

    async def _validate_lines(self, company_id: UUID, branch_id: UUID | None, lines) -> None:
        if len(lines) < 2:
            raise TransactionValidationError("A transaction requires at least two lines.")
        for line in lines:
            account_id = line.account_id if hasattr(line, "account_id") else line["account_id"]
            account = await self.repository.account(company_id, account_id)
            if account is None:
                raise TransactionValidationError("Every account must belong to the transaction company.")
            if not account.is_active or account.is_group:
                raise TransactionValidationError("Transaction lines require active ledger accounts.")
            if account.branch_id not in (None, branch_id):
                raise TransactionValidationError("Every account must belong to the transaction branch.")

    @classmethod
    def _validate_balance(cls, lines) -> None:
        debit = sum(
            (cls._money(line.debit if hasattr(line, "debit") else line["debit"]) for line in lines),
            ZERO,
        )
        credit = sum(
            (cls._money(line.credit if hasattr(line, "credit") else line["credit"]) for line in lines),
            ZERO,
        )
        if debit <= ZERO or debit != credit:
            raise TransactionValidationError(
                f"Transaction is unbalanced: debits={debit}, credits={credit}."
            )

    async def _number(
        self,
        company_id: UUID,
        branch_id: UUID | None,
        year_id: UUID,
        requested: str | None,
    ) -> str:
        if requested is not None:
            value = requested.strip()
            if not value:
                raise TransactionValidationError("Transaction number cannot be blank.")
            return value
        sequence = await self.numbering.get_by_scope(company_id, "transaction", branch_id, year_id)
        if sequence is None:
            sequence = await self.numbering.get_by_scope(company_id, "transaction", branch_id, None)
        if sequence is not None:
            allocation = await self.numbering.increment(sequence.id)
            if allocation is None:
                raise TransactionValidationError("Transaction number sequence is inactive.")
            number, sequence = allocation
            return sequence.format_number(number)
        return f"TXN-{uuid4().hex[:16].upper()}"

    @staticmethod
    def _payload(data: TransactionCreate | dict[str, Any] | None, values: dict[str, Any]) -> dict[str, Any]:
        if data is None:
            return values
        if values:
            if isinstance(data, TransactionCreate):
                return {**data.model_dump(), **values}
            return {**data, **values}
        return data.model_dump() if isinstance(data, TransactionCreate) else data

    @staticmethod
    def _money(value: Decimal | int | str) -> Decimal:
        return Decimal(str(value)).quantize(Decimal("0.01"))

    @staticmethod
    def _string(value: Any) -> str | None:
        return None if value is None else str(value)

    def _audit(
        self,
        transaction: Transaction,
        actor_id: UUID | None,
        action: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.session.add(
            AuditLog(
                company_id=transaction.company_id,
                branch_id=transaction.branch_id,
                user_id=actor_id,
                action=action,
                entity_type="transaction",
                entity_id=transaction.id,
                details=json.dumps(details or {}, default=str),
            )
        )


# Short alias used by integrations that call the engine a journal service.
TransactionService = FinancialTransactionService
