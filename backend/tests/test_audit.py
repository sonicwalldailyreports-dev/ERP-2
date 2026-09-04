from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, update

from app.core.audit import redact_sensitive
from app.db.models import AuditLog, Company, UserCompany
from app.modules.audit.schemas import AuditLogFilters
from app.modules.audit.service import AuditService
from tests.conftest import TEST_USER_ID


@pytest.mark.asyncio
async def test_audit_viewer_requires_authentication(test_app):
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        response = await client.get("/api/v1/audit/logs")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_audit_insert_redacts_sensitive_values_and_is_append_only(test_app):
    async with test_app.state.session_factory() as session:
        row = AuditLog(
            user_id=TEST_USER_ID,
            action="PASSWORD_CHANGED",
            entity_type="user",
            details='{"password":"do-not-store","token":"also-secret","name":"safe"}',
        )
        session.add(row)
        await session.commit()
        await session.refresh(row)
        assert row.after_data == {
            "password": "[REDACTED]",
            "token": "[REDACTED]",
            "name": "safe",
        }
        with pytest.raises(ValueError, match="append-only"):
            await session.execute(update(AuditLog).values(action="TAMPERED"))
        await session.rollback()
        with pytest.raises(ValueError, match="append-only"):
            await session.execute(delete(AuditLog))


@pytest.mark.asyncio
async def test_audit_viewer_filters_and_paginates(test_app):
    async with test_app.state.session_factory() as session:
        session.add_all(
            [
                AuditLog(user_id=TEST_USER_ID, action="CREATE", module="customers", entity_type="customer"),
                AuditLog(user_id=TEST_USER_ID, action="DELETE", module="customers", entity_type="customer"),
            ]
        )
        await session.commit()
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        response = await client.get(
            "/api/v1/audit/logs",
            params={"action": "CREATE", "page": 1, "page_size": 1},
            headers={"X-Dev-User-ID": str(TEST_USER_ID)},
        )
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["action"] == "CREATE"
    assert payload["pages"] == 1


@pytest.mark.asyncio
async def test_audit_service_enforces_tenant_isolation(test_app):
    company_a, company_b = uuid4(), uuid4()
    async with test_app.state.session_factory() as session:
        session.add_all(
            [
                Company(id=company_a, name="Tenant A", code=f"A-{company_a.hex[:8]}"),
                Company(id=company_b, name="Tenant B", code=f"B-{company_b.hex[:8]}"),
            ]
        )
        await session.flush()
        session.add_all(
            [
                UserCompany(user_id=TEST_USER_ID, company_id=company_a),
                AuditLog(company_id=company_a, action="A", module="test", entity_type="record"),
                AuditLog(company_id=company_b, action="B", module="test", entity_type="record"),
            ]
        )
        await session.commit()
        result = await AuditService(session).list(
            TEST_USER_ID,
            AuditLogFilters(page=1, page_size=100),
            dev=False,
        )
    assert result["total"] == 1
    assert result["items"][0].action == "A"
    assert redact_sensitive({"refresh_token": "secret"})["refresh_token"] == "[REDACTED]"
