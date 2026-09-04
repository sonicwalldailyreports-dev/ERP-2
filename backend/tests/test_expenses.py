from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.db.models import Account, AccountType, CashTransaction, FinancialYear
from tests.conftest import TEST_USER_ID


async def _setup(test_app, client: AsyncClient):
    headers = {"X-Dev-User-ID": str(TEST_USER_ID)}
    company = (
        await client.post(
            "/api/v1/companies",
            json={"name": f"Expense {uuid4().hex[:6]}", "code": uuid4().hex[:10]},
            headers=headers,
        )
    ).json()
    company_id = UUID(company["id"])
    async with test_app.state.session_factory() as session:
        year = FinancialYear(
            company_id=company_id,
            name="2026-27",
            start_date=date(2026, 4, 1),
            end_date=date(2027, 3, 31),
        )
        account_type = AccountType(company_id=None, code="expense", name="Expense")
        session.add_all([year, account_type])
        await session.flush()
        account = Account(
            company_id=company_id,
            account_code="OFFICE",
            name="Office expenses",
            account_type_id=account_type.id,
        )
        session.add(account)
        await session.commit()
        year_id, account_id = str(year.id), str(account.id)
    category = (
        await client.post(
            "/api/v1/expenses/categories",
            json={"company_id": company["id"], "code": "TRAVEL", "name": "Travel"},
            headers=headers,
        )
    ).json()
    cash = (
        await client.post(
            "/api/v1/cash-book/accounts",
            json={"company_id": company["id"], "account_code": "BANK", "name": "Bank"},
            headers=headers,
        )
    ).json()
    return company, year_id, account_id, category, cash, headers


@pytest.mark.asyncio
async def test_expense_workflow_posts_atomic_cash_entry_and_reverses(test_app):
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        company, year_id, account_id, category, cash, headers = await _setup(test_app, client)
        created = await client.post(
            "/api/v1/expenses",
            json={
                "company_id": company["id"],
                "financial_year_id": year_id,
                "date": "2026-05-01",
                "category_id": category["id"],
                "account_id": account_id,
                "amount": "100.00",
                "tax_amount": "10.00",
                "payment_method": "cash",
                "cash_account_id": cash["id"],
                "attachment": {"name": "receipt.pdf", "content_type": "application/pdf", "size": 42},
            },
            headers=headers,
        )
        assert created.status_code == 201
        expense_id = created.json()["id"]
        for action in ("submit", "approve", "post"):
            assert (
                await client.post(f"/api/v1/expenses/{expense_id}/{action}", headers=headers)
            ).status_code == 200
        posted = await client.get(f"/api/v1/expenses/{expense_id}", headers=headers)
        assert posted.json()["status"] == "POSTED"
        assert (
            await client.patch(
                f"/api/v1/expenses/{expense_id}", json={"amount": "999"}, headers=headers
            )
        ).status_code == 409
        async with test_app.state.session_factory() as session:
            entry = await session.scalar(
                select(CashTransaction).where(
                    CashTransaction.source_expense_id == UUID(expense_id)
                )
            )
            assert entry is not None and entry.amount == Decimal("110.00")
        reversal = await client.post(f"/api/v1/expenses/{expense_id}/reverse", headers=headers)
        assert reversal.status_code == 201
        assert reversal.json()["reversal_of_id"] == expense_id
        assert (
            await client.post(f"/api/v1/expenses/{expense_id}/reverse", headers=headers)
        ).status_code == 409


@pytest.mark.asyncio
async def test_expense_date_and_payment_validation(test_app):
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        company, year_id, account_id, category, _cash, headers = await _setup(test_app, client)
        payload = {
            "company_id": company["id"],
            "financial_year_id": year_id,
            "date": "2028-01-01",
            "category_id": category["id"],
            "account_id": account_id,
            "amount": "10.00",
            "payment_method": "cash",
        }
        assert (await client.post("/api/v1/expenses", json=payload, headers=headers)).status_code == 422
        payload["date"] = "2026-05-01"
        assert (await client.post("/api/v1/expenses", json=payload, headers=headers)).status_code == 422
