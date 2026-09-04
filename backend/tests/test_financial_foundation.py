import asyncio
from datetime import date
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db.models import Account, AccountType, Company, FinancialYear, NumberSequence
from app.modules.numbering.repository import NumberSequenceRepository
from tests.conftest import TEST_USER_ID


@pytest_asyncio.fixture
async def financial_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    @event.listens_for(engine.sync_engine, "connect")
    def enable_foreign_keys(dbapi_connection, _):
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


async def _company(session: AsyncSession) -> Company:
    company = Company(name=f"Finance {uuid4().hex[:6]}", code=uuid4().hex[:10].upper())
    session.add(company)
    await session.flush()
    return company


async def test_account_hierarchy_and_tenant_validation(financial_session: AsyncSession) -> None:
    company = await _company(financial_session)
    other = await _company(financial_session)
    account_type = AccountType(code="asset", name="Asset")
    financial_session.add(account_type)
    await financial_session.flush()
    parent = Account(
        company_id=company.id,
        account_code="1000",
        name="Assets",
        account_type_id=account_type.id,
        is_group=True,
    )
    financial_session.add(parent)
    await financial_session.flush()
    child = Account(
        company_id=company.id,
        account_code="1001",
        name="Cash",
        account_type_id=account_type.id,
        parent_account_id=parent.id,
    )
    financial_session.add(child)
    await financial_session.commit()
    assert child.parent_account_id == parent.id
    assert other.id != company.id
    assert (await financial_session.scalar(select(Account).where(Account.company_id == other.id))) is None


async def test_number_sequence_format_and_financial_year_validation(financial_session: AsyncSession) -> None:
    company = await _company(financial_session)
    year = FinancialYear(
        company_id=company.id,
        name="2026-27",
        start_date=date(2026, 4, 1),
        end_date=date(2027, 3, 31),
    )
    financial_session.add(year)
    await financial_session.flush()
    assert year.contains(date(2026, 4, 1))
    assert not year.contains(date(2027, 4, 1))
    sequence = NumberSequence(
        company_id=company.id,
        financial_year_id=year.id,
        document_type="invoice",
        scope_key=f"{company.id}:*:{year.id}:invoice",
        prefix="INV",
        separator="-",
        number_padding=6,
    )
    financial_session.add(sequence)
    await financial_session.commit()
    assert sequence.format_number(12) == "INV-000012"
    with pytest.raises(ValueError):
        year.validate_date(date(2027, 4, 1))


async def test_number_sequence_concurrent_allocations() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    company_id = uuid4()
    sequence_id = uuid4()
    async with factory() as session:
        session.add(Company(id=company_id, name="Concurrent", code=uuid4().hex[:10].upper()))
        session.add(
            NumberSequence(
                id=sequence_id,
                company_id=company_id,
                document_type="receipt",
                scope_key=f"{company_id}:*:*:receipt",
            )
        )
        await session.commit()

    async def allocate() -> int:
        async with factory() as session:
            result = await NumberSequenceRepository(session).increment(sequence_id)
            assert result is not None
            await session.commit()
            return result[0]

    values = await asyncio.gather(*(allocate() for _ in range(20)))
    assert sorted(values) == list(range(1, 21))
    await engine.dispose()


async def test_account_and_numbering_api(test_app) -> None:
    headers = {"X-Dev-User-ID": str(TEST_USER_ID)}
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        company = (
            await client.post(
                "/api/v1/companies",
                json={"name": "Foundation", "code": f"F-{uuid4().hex[:8]}"},
                headers=headers,
            )
        ).json()
        types = (await client.get("/api/v1/accounts/types", headers=headers)).json()
        assert {item["code"] for item in types} == {
            "cash",
            "bank",
            "customer",
            "vendor",
            "income",
            "expense",
            "asset",
            "liability",
            "equity",
        }
        account = await client.post(
            "/api/v1/accounts",
            json={
                "company_id": company["id"],
                "account_code": "1100",
                "name": "Cash",
                "account_type_id": next(item["id"] for item in types if item["code"] == "cash"),
                "is_group": True,
            },
            headers=headers,
        )
        assert account.status_code == 201
        sequence = await client.post(
            "/api/v1/number-sequences",
            json={
                "company_id": company["id"],
                "document_type": "invoice",
                "prefix": "INV",
                "separator": "/",
                "number_padding": 3,
            },
            headers=headers,
        )
        assert sequence.status_code == 201
        generated = await client.post(
            "/api/v1/number-sequences/next",
            json={"sequence_id": sequence.json()["id"]},
            headers=headers,
        )
        assert generated.json()["formatted_number"] == "INV/001"
