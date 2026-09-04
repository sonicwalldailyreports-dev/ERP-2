from datetime import date
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db.models import Branch, Company, FinancialYear, UserBranch


@pytest_asyncio.fixture
async def db_session():
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


async def test_company_and_branch_relationship_constraints(db_session):
    company = Company(name="Acme", code="ACME")
    other_company = Company(name="Other", code="OTHER")
    db_session.add_all([company, other_company])
    await db_session.flush()
    branch = Branch(company_id=company.id, name="Main", code="MAIN")
    db_session.add(branch)
    await db_session.flush()
    db_session.add(UserBranch(user_id=uuid4(), branch_id=branch.id, company_id=other_company.id))
    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_unique_company_code(db_session):
    db_session.add_all([Company(name="One", code="DUP"), Company(name="Two", code="DUP")])
    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_financial_year_date_constraint(db_session):
    company = Company(name="Acme", code="ACME")
    db_session.add(company)
    await db_session.flush()
    db_session.add(FinancialYear(
        company_id=company.id,
        name="Invalid",
        start_date=date(2026, 4, 1),
        end_date=date(2026, 3, 31),
    ))
    with pytest.raises(IntegrityError):
        await db_session.flush()
