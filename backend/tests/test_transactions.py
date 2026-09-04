import asyncio
from datetime import date
from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db.models import Account, AccountType, AuditLog, Company, FinancialYear, Transaction
from app.modules.transactions.service import (
    DuplicateTransactionNumberError,
    FinancialTransactionService,
    TransactionStateError,
    TransactionValidationError,
)


@pytest_asyncio.fixture
async def transaction_context():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    @event.listens_for(engine.sync_engine, "connect")
    def enable_foreign_keys(dbapi_connection, _):
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        company = Company(name="Ledger Co", code="LEDGER")
        other = Company(name="Other Co", code="OTHER")
        session.add_all([company, other])
        await session.flush()
        year = FinancialYear(
            company_id=company.id,
            name="2026-27",
            start_date=date(2026, 4, 1),
            end_date=date(2027, 3, 31),
        )
        account_type = AccountType(code="asset", name="Asset")
        session.add_all([year, account_type])
        await session.flush()
        debit = Account(
            company_id=company.id, account_code="1000", name="Debit", account_type_id=account_type.id
        )
        credit = Account(
            company_id=company.id, account_code="2000", name="Credit", account_type_id=account_type.id
        )
        session.add_all([debit, credit])
        await session.commit()
        yield factory, company, other, year, debit, credit
    await engine.dispose()


def _payload(company, year, debit, credit, **extra):
    return {
        "company_id": company.id,
        "financial_year_id": year.id,
        "transaction_date": date(2026, 5, 1),
        "lines": [
            {"account_id": debit.id, "debit": Decimal("100.00")},
            {"account_id": credit.id, "credit": Decimal("100.00")},
        ],
        **extra,
    }


@pytest.mark.asyncio
async def test_balanced_and_unbalanced_transactions(transaction_context):
    factory, company, _, year, debit, credit = transaction_context
    async with factory() as session:
        service = FinancialTransactionService(session)
        transaction = await service.create(_payload(company, year, debit, credit))
        assert transaction.status == "DRAFT"
        with pytest.raises(TransactionValidationError, match="unbalanced"):
            await service.create(
                _payload(
                    company,
                    year,
                    debit,
                    credit,
                    lines=[
                        {"account_id": debit.id, "debit": Decimal("100.00")},
                        {"account_id": credit.id, "credit": Decimal("90.00")},
                    ],
                )
            )


@pytest.mark.asyncio
async def test_posting_is_audited_and_immutable(transaction_context):
    factory, company, _, year, debit, credit = transaction_context
    async with factory() as session:
        service = FinancialTransactionService(session)
        transaction = await service.create(_payload(company, year, debit, credit))
        posted = await service.post(transaction.id)
        assert posted.status == "POSTED"
        audit = await session.scalar(
            select(AuditLog).where(AuditLog.entity_id == transaction.id, AuditLog.action == "TRANSACTION_POSTED")
        )
        assert audit is not None
        posted.description = "not allowed"
        with pytest.raises(ValueError, match="immutable"):
            await session.commit()
        await session.rollback()


@pytest.mark.asyncio
async def test_duplicate_number_and_reversal(transaction_context):
    factory, company, _, year, debit, credit = transaction_context
    async with factory() as session:
        service = FinancialTransactionService(session)
        payload = _payload(company, year, debit, credit, transaction_number="J-001")
        transaction = await service.create(payload)
        with pytest.raises(DuplicateTransactionNumberError):
            await service.create(payload)
        await service.post(transaction.id)
        reversal = await service.reverse(transaction.id)
        assert reversal.reversal_of_id == transaction.id
        assert reversal.lines[0].debit == Decimal("0.00")
        assert reversal.lines[0].credit == Decimal("100.00")
        with pytest.raises(TransactionStateError):
            await service.reverse(transaction.id)


@pytest.mark.asyncio
async def test_financial_year_and_tenant_validation(transaction_context):
    factory, company, other, year, debit, credit = transaction_context
    async with factory() as session:
        service = FinancialTransactionService(session)
        with pytest.raises(TransactionValidationError, match="outside"):
            await service.create(
                _payload(
                    company,
                    year,
                    debit,
                    credit,
                    transaction_date=date(2028, 1, 1),
                )
            )
        with pytest.raises(TransactionValidationError, match="company"):
            await service.create(
                _payload(
                    other,
                    year,
                    debit,
                    credit,
                )
            )


@pytest.mark.asyncio
async def test_concurrent_creation_allocates_unique_numbers(transaction_context):
    factory, company, _, year, debit, credit = transaction_context

    async def create_one():
        async with factory() as session:
            return await FinancialTransactionService(session).create(
                _payload(company, year, debit, credit)
            )

    transactions = await asyncio.gather(*(create_one() for _ in range(10)))
    assert len({item.transaction_number for item in transactions}) == 10
    async with factory() as session:
        assert len(
            (
                await session.scalars(
                    select(Transaction).where(Transaction.company_id == company.id)
                )
            ).all()
        ) == 10
