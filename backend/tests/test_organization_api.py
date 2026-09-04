from uuid import UUID

from httpx import ASGITransport, AsyncClient

from tests.conftest import TEST_USER_ID


async def test_company_and_branch_crud_and_audit(test_app) -> None:
    headers = {"X-Dev-User-ID": str(TEST_USER_ID)}
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        company_response = await client.post("/api/v1/companies", json={"name": "Acme", "code": "ACME"}, headers=headers)
        assert company_response.status_code == 201
        company = company_response.json()
        branch_response = await client.post(
            f"/api/v1/companies/{company['id']}/branches",
            json={"company_id": company["id"], "name": "Main", "code": "MAIN"},
            headers=headers,
        )
        assert branch_response.status_code == 201
        branch = branch_response.json()
        assert branch["company_id"] == company["id"]
        assert (await client.post(f"/api/v1/companies/{company['id']}/deactivate", headers=headers)).status_code == 200
        assert (await client.get("/api/v1/companies", headers=headers)).json()[0]["code"] == "ACME"


async def test_unassigned_company_isolation(test_app) -> None:
    company_id = UUID("00000000-0000-0000-0000-000000000099")
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        response = await client.get(f"/api/v1/companies/{company_id}", headers={"X-Dev-User-ID": str(TEST_USER_ID)})
    assert response.status_code == 404


async def test_company_id_mismatch_is_rejected(test_app) -> None:
    headers = {"X-Dev-User-ID": str(TEST_USER_ID)}
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        company = (await client.post("/api/v1/companies", json={"name": "Acme", "code": "ACME"}, headers=headers)).json()
        response = await client.post(
            f"/api/v1/companies/{company['id']}/branches",
            json={"company_id": str(UUID("00000000-0000-0000-0000-000000000099")), "name": "Wrong", "code": "WRONG"},
            headers=headers,
        )
    assert response.status_code == 422
