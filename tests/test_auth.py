import httpx
import pytest


@pytest.mark.asyncio
async def test_login_success(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": "admin@example.com", "password": "AdminPass123!"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["token_type"] == "bearer"
    assert body["data"]["user"]["is_admin"] is True
    assert "password_hash" not in body["data"]["user"]


@pytest.mark.asyncio
async def test_login_failure(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": "wrong"}
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"


@pytest.mark.asyncio
async def test_protected_endpoint(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401
    assert response.json() == {
        "success": False,
        "error": {"code": "AUTHENTICATION_REQUIRED", "message": "Authentication required"},
    }


@pytest.mark.asyncio
async def test_unknown_endpoint_uses_error_envelope(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/v1/not-a-real-endpoint")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "ENDPOINT_NOT_FOUND"
