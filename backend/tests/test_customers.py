from uuid import UUID, uuid4

from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.db.models import (
    AuditLog,
    Branch,
    Company,
    Customer,
    Permission,
    Role,
    RolePermission,
    UserBranch,
    UserCompany,
    UserRole,
)
from tests.conftest import TEST_USER_ID


async def test_customer_crud_search_filter_pagination_and_audit(test_app) -> None:
    headers = {"X-Dev-User-ID": str(TEST_USER_ID)}
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        company = (
            await client.post("/api/v1/companies", json={"name": "Customers Co", "code": "CUST"}, headers=headers)
        ).json()
        create = await client.post(
            f"/api/v1/customers?company_id={company['id']}",
            json={"customer_code": "c-001", "name": "Ada Lovelace", "email": "ada@example.com", "city": "London"},
            headers=headers,
        )
        assert create.status_code == 201
        customer = create.json()
        duplicate = await client.post(
            f"/api/v1/customers?company_id={company['id']}",
            json={"customer_code": "C-001", "name": "Duplicate"},
            headers=headers,
        )
        assert duplicate.status_code == 409
        second = await client.post(
            f"/api/v1/customers?company_id={company['id']}",
            json={"customer_code": "C-002", "name": "Grace Hopper"},
            headers=headers,
        )
        assert second.status_code == 201
        assert (await client.patch(f"/api/v1/customers/{customer['id']}", json={"phone": "123"}, headers=headers)).status_code == 200
        listing = await client.get(
            f"/api/v1/customers?company_id={company['id']}&search=ada&page=1&page_size=1", headers=headers
        )
        assert listing.json()["total"] == 1
        assert listing.json()["items"][0]["phone"] == "123"
        assert (await client.post(f"/api/v1/customers/{customer['id']}/deactivate", headers=headers)).json()["status"] == "inactive"
        filtered = await client.get(
            f"/api/v1/customers?company_id={company['id']}&status=inactive&page=1&page_size=1",
            headers=headers,
        )
        assert filtered.json()["total"] == 1
        paged = await client.get(
            f"/api/v1/customers?company_id={company['id']}&page=1&page_size=1", headers=headers
        )
        assert paged.json()["pages"] == 2
    async with test_app.state.session_factory() as session:
        audit = list(
            await session.scalars(
                select(AuditLog).where(
                    AuditLog.entity_type == "customer", AuditLog.entity_id == UUID(customer["id"])
                )
            )
        )
        assert {row.action for row in audit} >= {"CUSTOMER_CREATED", "CUSTOMER_UPDATED", "CUSTOMER_DEACTIVATED"}


async def test_customer_company_and_branch_isolation(test_app) -> None:
    company_a, company_b, branch_a, branch_b = uuid4(), uuid4(), uuid4(), uuid4()
    permission = Permission(code="customers.customer.view")
    role = Role(company_id=company_a, name="Customer viewer")
    async with test_app.state.session_factory() as session:
        session.add_all([
            Company(id=company_a, name="A", code=f"A-{company_a.hex[:8]}"),
            Company(id=company_b, name="B", code=f"B-{company_b.hex[:8]}"),
        ])
        await session.flush()
        session.add_all([
            Branch(id=branch_a, company_id=company_a, name="A branch", code="A1"),
            Branch(id=branch_b, company_id=company_a, name="B branch", code="B1"),
            permission,
            role,
        ])
        await session.flush()
        customer = Customer(company_id=company_b, customer_code="OTHER", name="Other company")
        session.add(customer)
        await session.flush()
        session.add_all([
            UserCompany(user_id=TEST_USER_ID, company_id=company_a),
            UserBranch(user_id=TEST_USER_ID, company_id=company_a, branch_id=branch_a),
            UserRole(user_id=TEST_USER_ID, role_id=role.id),
            RolePermission(role_id=role.id, permission_id=permission.id),
        ])
        await session.commit()
        other_id = customer.id
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        login = await client.post(
            "/api/v1/auth/login", json={"username": "test@example.com", "password": "test-password-123"}
        )
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        assert (await client.get(f"/api/v1/customers/{other_id}", headers=headers)).status_code == 403
        assert (await client.get(f"/api/v1/customers?company_id={company_a}&branch_id={branch_b}", headers=headers)).status_code == 403
