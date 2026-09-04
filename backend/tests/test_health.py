from httpx import ASGITransport, AsyncClient


async def test_health(test_app) -> None:
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        response = await client.get("/api/v1/health", headers={"X-Request-ID": "test-request"})

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.headers["X-Request-ID"] == "test-request"


async def test_readiness(test_app) -> None:
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        response = await client.get("/api/v1/readiness")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}
