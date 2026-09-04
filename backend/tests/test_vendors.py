from uuid import UUID, uuid4

from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.db.models import (
    AuditLog,
    Branch,
    Company,
    Permission,
    Role,
    RolePermission,
    UserBranch,
    UserCompany,
    UserRole,
    Vendor,
)
from tests.conftest import TEST_USER_ID


async def test_vendor_crud_search_filter_pagination_soft_delete_and_audit(test_app) -> None:
    headers = {"X-Dev-User-ID": str(TEST_USER_ID)}
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        company = (await client.post("/api/v1/companies", json={"name": "Vendors Co", "code": "VEND"}, headers=headers)).json()
        create = await client.post(
            f"/api/v1/vendors?company_id={company['id']}",
            json={"vendor_code": "v-001", "vendor_name": "Acme Supplies", "email": "acme@example.com", "city": "London"},
            headers=headers,
        )
        assert create.status_code == 201
        vendor = create.json()
        duplicate = await client.post(
            f"/api/v1/vendors?company_id={company['id']}",
            json={"vendor_code": "V-001", "name": "Duplicate"},
            headers=headers,
        )
        assert duplicate.status_code == 409
        second = await client.post(
            f"/api/v1/vendors?company_id={company['id']}",
            json={"vendor_code": "V-002", "name": "Bravo Trading"},
            headers=headers,
        )
        assert second.status_code == 201
        assert (await client.patch(f"/api/v1/vendors/{vendor['id']}", json={"phone": "123"}, headers=headers)).status_code == 200
        listing = await client.get(
            f"/api/v1/vendors?company_id={company['id']}&search=acme&page=1&page_size=1", headers=headers
        )
        assert listing.json()["total"] == 1
        assert listing.json()["items"][0]["phone"] == "123"
        assert (await client.post(f"/api/v1/vendors/{vendor['id']}/deactivate", headers=headers)).json()["status"] == "inactive"
        filtered = await client.get(
            f"/api/v1/vendors?company_id={company['id']}&status=inactive&page=1&page_size=1", headers=headers
        )
        assert filtered.json()["total"] == 1
        paged = await client.get(f"/api/v1/vendors?company_id={company['id']}&page=1&page_size=1", headers=headers)
        assert paged.json()["pages"] == 2
        deleted = await client.delete(f"/api/v1/vendors/{vendor['id']}", headers=headers)
        assert deleted.status_code == 200
        assert (await client.get(f"/api/v1/vendors/{vendor['id']}", headers=headers)).status_code == 404
        assert (await client.get(f"/api/v1/vendors?company_id={company['id']}", headers=headers)).json()["total"] == 1
    async with test_app.state.session_factory() as session:
        audit = list(await session.scalars(select(AuditLog).where(
            AuditLog.entity_type == "vendor", AuditLog.entity_id == UUID(vendor["id"])
        )))
        assert {row.action for row in audit} >= {
            "VENDOR_CREATED", "VENDOR_UPDATED", "VENDOR_DEACTIVATED", "VENDOR_DELETED"
        }


async def test_vendor_company_and_branch_isolation(test_app) -> None:
    company_a, company_b, branch_a, branch_b = uuid4(), uuid4(), uuid4(), uuid4()
    permission = Permission(code="vendors.vendor.view")
    role = Role(company_id=company_a, name="Vendor viewer")
    async with test_app.state.session_factory() as session:
        session.add_all([
            Company(id=company_a, name="A", code=f"A-{company_a.hex[:8]}"),
            Company(id=company_b, name="B", code=f"B-{company_b.hex[:8]}"),
        ])
        await session.flush()
        session.add_all([
            Branch(id=branch_a, company_id=company_a, name="A branch", code="A1"),
            Branch(id=branch_b, company_id=company_a, name="B branch", code="B1"),
            permission, role,
        ])
        await session.flush()
        vendor = Vendor(company_id=company_b, vendor_code="OTHER", name="Other company")
        session.add(vendor)
        await session.flush()
        session.add_all([
            UserCompany(user_id=TEST_USER_ID, company_id=company_a),
            UserBranch(user_id=TEST_USER_ID, company_id=company_a, branch_id=branch_a),
            UserRole(user_id=TEST_USER_ID, role_id=role.id),
            RolePermission(role_id=role.id, permission_id=permission.id),
        ])
        await session.commit()
        other_id = vendor.id
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        login = await client.post(
            "/api/v1/auth/login", json={"username": "test@example.com", "password": "test-password-123"}
        )
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        assert (await client.get(f"/api/v1/vendors/{other_id}", headers=headers)).status_code == 403
        assert (await client.get(f"/api/v1/vendors?company_id={company_a}&branch_id={branch_b}", headers=headers)).status_code == 403
