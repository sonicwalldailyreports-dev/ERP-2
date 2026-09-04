from uuid import uuid4

from httpx import ASGITransport, AsyncClient

from app.db.models import Branch, Company
from tests.conftest import TEST_USER_ID


def dev_headers() -> dict[str, str]:
    return {"X-Dev-User-ID": str(TEST_USER_ID)}


async def test_user_management_crud_assignments_and_audit(test_app) -> None:
    company_id, branch_id = uuid4(), uuid4()
    async with test_app.state.session_factory() as session:
        session.add(Company(id=company_id, name="Users Co", code=f"U-{company_id.hex[:8]}"))
        await session.flush()
        session.add(Branch(id=branch_id, company_id=company_id, name="Main", code="MAIN"))
        await session.commit()
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        created = await client.post(
            "/api/v1/users",
            headers=dev_headers(),
            json={
                "username": "managed", "email": "managed@example.com", "full_name": "Managed User",
                "password": "managed-password-123", "company_ids": [str(company_id)],
                "branch_assignments": [{"company_id": str(company_id), "branch_id": str(branch_id)}],
            },
        )
        assert created.status_code == 201
        user = created.json()
        assert user["company_ids"] == [str(company_id)]
        listing = await client.get(f"/api/v1/users?company_id={company_id}&search=managed", headers=dev_headers())
        assert listing.status_code == 200
        assert listing.json()["total"] == 1
        updated = await client.patch(
            f"/api/v1/users/{user['id']}", headers=dev_headers(), json={"phone": "555-0100"}
        )
        assert updated.status_code == 200
        activity = await client.get(f"/api/v1/users/{user['id']}/audit-activity", headers=dev_headers())
        assert activity.status_code == 200
        assert len(activity.json()) >= 2


async def test_user_cannot_deactivate_self(test_app) -> None:
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        response = await client.post(
            f"/api/v1/users/{TEST_USER_ID}/deactivate", headers=dev_headers()
        )
    assert response.status_code == 422
