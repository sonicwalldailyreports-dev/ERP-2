from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.db.models import AuditLog, CashTransaction, FinancialYear
from tests.conftest import TEST_USER_ID


async def _setup(test_app, client: AsyncClient) -> tuple[dict, dict, str, dict[str, str]]:
    headers = {"X-Dev-User-ID": str(TEST_USER_ID)}
    company = (await client.post("/api/v1/companies", json={"name": f"Cash {uuid4().hex[:6]}", "code": uuid4().hex[:10]}, headers=headers)).json()
    async with test_app.state.session_factory() as session:
        year = FinancialYear(company_id=UUID(company["id"]), name="2026-27", start_date=date(2026, 4, 1), end_date=date(2027, 3, 31))
        session.add(year)
        await session.commit()
        year_id = str(year.id)
    account = (await client.post("/api/v1/cash-book/accounts", json={"company_id": company["id"], "account_code": "CASH", "name": "Office cash", "opening_balance": "25.00"}, headers=headers)).json()
    return company, account, year_id, headers


@pytest.mark.asyncio
async def test_cashbook_workflow_balance_reversal_and_immutability(test_app) -> None:
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        company, account, year_id, headers = await _setup(test_app, client)
        payload = {"company_id": company["id"], "cash_account_id": account["id"], "financial_year_id": year_id, "transaction_type": "receipt", "transaction_date": "2026-05-01", "amount": "100.00", "reference": "R-1"}
        created = await client.post("/api/v1/cash-book/transactions", json=payload, headers=headers)
        assert created.status_code == 201
        transaction_id = created.json()["id"]
        for action in ("submit", "approve", "post"):
            assert (await client.post(f"/api/v1/cash-book/transactions/{transaction_id}/{action}", headers=headers)).status_code == 200
        assert (await client.patch(f"/api/v1/cash-book/transactions/{transaction_id}", json={"amount": "999.00"}, headers=headers)).status_code == 409
        accounts = await client.get(f"/api/v1/cash-book/accounts?company_id={company['id']}", headers=headers)
        assert Decimal(str(accounts.json()[0]["balance"])) == Decimal("125.00")
        reversal = await client.post(f"/api/v1/cash-book/transactions/{transaction_id}/reverse", headers=headers)
        assert reversal.status_code == 201
        assert reversal.json()["reversal_of_id"] == transaction_id
        assert (await client.post(f"/api/v1/cash-book/transactions/{transaction_id}/reverse", headers=headers)).status_code == 409
        history = await client.get(f"/api/v1/cash-book/transactions/{transaction_id}/history", headers=headers)
        assert {event["action"] for event in history.json()} >= {"CASH_TRANSACTION_CREATED", "CASH_TRANSACTION_POSTED", "CASH_TRANSACTION_REVERSED"}


@pytest.mark.asyncio
async def test_cashbook_validation_and_daily_summary(test_app) -> None:
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        company, account, year_id, headers = await _setup(test_app, client)
        bad_date = await client.post("/api/v1/cash-book/transactions", json={
            "company_id": company["id"], "cash_account_id": account["id"], "financial_year_id": year_id,
            "transaction_type": "payment", "transaction_date": "2028-01-01", "amount": "10.00",
        }, headers=headers)
        assert bad_date.status_code == 422
        bad_transfer = await client.post("/api/v1/cash-book/transactions", json={
            "company_id": company["id"], "cash_account_id": account["id"], "financial_year_id": year_id,
            "transaction_type": "transfer", "transaction_date": "2026-05-01", "amount": "10.00",
        }, headers=headers)
        assert bad_transfer.status_code == 422
        summary = await client.get(f"/api/v1/cash-book/daily-summary?company_id={company['id']}&summary_date=2026-05-01", headers=headers)
        assert summary.status_code == 200
        assert summary.json()[0]["closing_balance"] == "25.00"


@pytest.mark.asyncio
async def test_cashbook_company_isolation(test_app) -> None:
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        company, account, year_id, headers = await _setup(test_app, client)
        other = (await client.post("/api/v1/companies", json={"name": "Other", "code": uuid4().hex[:10]}, headers=headers)).json()
        response = await client.get(f"/api/v1/cash-book/accounts?company_id={other['id']}", headers=headers)
        assert response.status_code == 200 and response.json() == []
        transaction = CashTransaction(
            company_id=UUID(company["id"]), cash_account_id=UUID(account["id"]), financial_year_id=UUID(year_id),
            transaction_type="receipt", transaction_date=date(2026, 5, 1), amount=Decimal(5), state="DRAFT", created_by=TEST_USER_ID,
        )
        async with test_app.state.session_factory() as session:
            session.add(transaction)
            await session.commit()
            assert (await session.scalar(select(CashTransaction).where(CashTransaction.company_id == UUID(other["id"])))) is None
            assert (await session.scalar(select(AuditLog).where(AuditLog.entity_id == transaction.id))) is None
