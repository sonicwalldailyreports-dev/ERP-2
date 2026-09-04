from httpx import ASGITransport, AsyncClient


async def test_dashboard_requires_authentication(test_app) -> None:
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        response = await client.get("/api/v1/dashboard")

    assert response.status_code == 401


async def test_dashboard_requires_company_scope(test_app) -> None:
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        response = await client.get(
            "/api/v1/dashboard",
            headers={"X-Dev-User-ID": "00000000-0000-0000-0000-000000000001"},
        )

    assert response.status_code == 422
    assert "company_id" in response.json()["detail"]
