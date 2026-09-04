from datetime import date
from decimal import Decimal
from uuid import uuid4

from httpx import ASGITransport, AsyncClient

from app.db.models import Branch, CashAccount, CashTransaction, Company, FinancialYear
from tests.conftest import TEST_USER_ID


async def _seed_cash(test_app):
    company_id, branch_a, branch_b = uuid4(), uuid4(), uuid4()
    year_id, account_id = uuid4(), uuid4()
    async with test_app.state.session_factory() as session:
        session.add(
            Company(id=company_id, name="Reports Co", code=f"R-{company_id.hex[:10]}")
        )
        await session.flush()
        session.add_all(
            [
                Branch(id=branch_a, company_id=company_id, name="A", code="A"),
                Branch(id=branch_b, company_id=company_id, name="B", code="B"),
                FinancialYear(
                    id=year_id,
                    company_id=company_id,
                    name="2026",
                    start_date=date(2026, 1, 1),
                    end_date=date(2026, 12, 31),
                ),
                CashAccount(
                    id=account_id,
                    company_id=company_id,
                    branch_id=branch_a,
                    account_code="CASH",
                    name="Cash",
                ),
            ]
        )
        await session.flush()
        session.add_all(
            [
                CashTransaction(
                    company_id=company_id,
                    branch_id=branch_a,
                    cash_account_id=account_id,
                    financial_year_id=year_id,
                    transaction_type="receipt",
                    transaction_date=date(2026, 1, 2),
                    amount=Decimal("10.00"),
                    state="POSTED",
                ),
                CashTransaction(
                    company_id=company_id,
                    branch_id=branch_b,
                    cash_account_id=account_id,
                    financial_year_id=year_id,
                    transaction_type="receipt",
                    transaction_date=date(2026, 1, 2),
                    amount=Decimal("90.00"),
                    state="POSTED",
                ),
            ]
        )
        await session.commit()
    return company_id, branch_a, branch_b, year_id


async def test_report_branch_filter_and_totals(test_app) -> None:
    company_id, branch_a, _, year_id = await _seed_cash(test_app)
    params = {
        "company_id": str(company_id),
        "branch_id": str(branch_a),
        "financial_year_id": str(year_id),
    }
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        response = await client.get(
            "/api/v1/reports/cash-transactions",
            params=params,
            headers={"X-Dev-User-ID": str(TEST_USER_ID)},
        )
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["totals"]["receipts"] == "10.00"


async def test_report_company_isolation(test_app) -> None:
    company_id, _, _, year_id = await _seed_cash(test_app)
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        response = await client.get(
            "/api/v1/reports/cash-transactions",
            params={"company_id": str(uuid4()), "financial_year_id": str(year_id)},
            headers={"X-Dev-User-ID": str(TEST_USER_ID)},
        )
    assert response.status_code == 404
    assert company_id


async def test_report_requires_view_permission(test_app) -> None:
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        response = await client.get("/api/v1/reports/cash-summary")
    assert response.status_code == 401
