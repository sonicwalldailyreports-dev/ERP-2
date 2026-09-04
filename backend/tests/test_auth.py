from httpx import ASGITransport, AsyncClient

from app.core.config import get_settings
from app.modules.auth.service import AuthService
from tests.conftest import TEST_USER_ID


async def test_login_refresh_logout_and_me(test_app) -> None:
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        login = await client.post("/api/v1/auth/login", json={"username": "test@example.com", "password": "test-password-123"})
        assert login.status_code == 200
        tokens = login.json()
        assert tokens["access_token"] != tokens["refresh_token"]
        assert (await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"})).json()["id"] == str(TEST_USER_ID)
        refreshed = await client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
        assert refreshed.status_code == 200
        assert (await client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})).status_code == 401
        assert (await client.post("/api/v1/auth/logout", json={"refresh_token": refreshed.json()["refresh_token"]})).status_code == 204


async def test_failed_logins_lock_account(test_app) -> None:
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        for _ in range(5):
            response = await client.post("/api/v1/auth/login", json={"username": "test@example.com", "password": "wrong-password"})
        assert response.status_code == 401
        assert (await client.post("/api/v1/auth/login", json={"username": "test@example.com", "password": "test-password-123"})).status_code == 401


async def test_change_password_revokes_sessions(test_app) -> None:
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        login = await client.post("/api/v1/auth/login", json={"username": "test@example.com", "password": "test-password-123"})
        tokens = login.json()
        response = await client.post(
            "/api/v1/auth/change-password",
            json={"current_password": "test-password-123", "new_password": "new-test-password-123"},
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )
        assert response.status_code == 204
        assert (await client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})).status_code == 401


async def test_password_reset_is_generic_and_one_time(test_app) -> None:
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        request = await client.post("/api/v1/auth/password-reset/request", json={"email": "missing@example.com"})
        assert request.status_code == 202
        assert request.json() == {"message": "If the account exists, reset instructions will be sent."}

        service = test_app.state.session_factory
        async with service() as session:
            token = await AuthService(session, get_settings()).request_password_reset("test@example.com")

        assert token is not None
        reset = await client.post(
            "/api/v1/auth/password-reset/confirm",
            json={"token": token, "new_password": "reset-test-password-123"},
        )
        assert reset.status_code == 204
        reused = await client.post(
            "/api/v1/auth/password-reset/confirm",
            json={"token": token, "new_password": "reset-test-password-456"},
        )
        assert reused.status_code == 400
