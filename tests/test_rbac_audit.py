from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from sqlalchemy import func, select

from app.core.database import AsyncSessionFactory
from app.models.access import UserSession
from app.models.audit import AuditEvent
from app.models.product import Product
from app.models.stock_transaction import StockTransaction
from app.services.audit import audit_json


async def create_user(
    client: httpx.AsyncClient,
    admin_headers: dict[str, str],
    role: str,
    *,
    username: str | None = None,
) -> dict[str, Any]:
    username = username or f"{role}_account"
    response = await client.post(
        "/api/v1/users",
        headers=admin_headers,
        json={
            "username": username,
            "email": f"{username}@example.com",
            "full_name": f"{role.title()} Account",
            "role": role,
            "password": "StrongPass123!",
            "is_active": True,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


async def login(client: httpx.AsyncClient, username: str, password: str = "StrongPass123!"):
    response = await client.post(
        "/api/v1/auth/login", json={"username": username, "password": password}
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['data']['access_token']}"}


@pytest.mark.asyncio
async def test_login_returns_role_permissions_and_server_session(
    client: httpx.AsyncClient,
) -> None:
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "AdminPass123!"},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["user"]["role"] == "admin"
    assert "users.create" in data["user"]["effective_permissions"]

    headers = {"Authorization": f"Bearer {data['access_token']}"}
    sessions = await client.get("/api/v1/users/1/sessions", headers=headers)
    assert sessions.status_code == 200
    assert len(sessions.json()["data"]) == 1
    assert sessions.json()["data"][0]["revoked_at"] is None


@pytest.mark.asyncio
async def test_role_permission_matrix_and_live_reporter_toggle(
    client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    product_payload: dict,
) -> None:
    manager = await create_user(client, auth_headers, "manager")
    user = await create_user(client, auth_headers, "user")
    reporter = await create_user(client, auth_headers, "reporter")
    manager_headers = await login(client, manager["username"])
    user_headers = await login(client, user["username"])
    reporter_headers = await login(client, reporter["username"])

    assert (await client.get("/api/v1/dashboard", headers=manager_headers)).status_code == 200
    assert (await client.get("/api/v1/users", headers=manager_headers)).status_code == 403

    created = await client.post("/api/v1/products", json=product_payload, headers=manager_headers)
    assert created.status_code == 201
    product_id = created.json()["data"]["id"]

    assert (await client.get("/api/v1/products", headers=user_headers)).status_code == 200
    assert (
        await client.post(
            f"/api/v1/products/{product_id}/stock/out",
            json={"quantity": "1"},
            headers=user_headers,
        )
    ).status_code == 201
    forbidden = [
        ("get", "/api/v1/dashboard", None),
        ("get", "/api/v1/reports/products", None),
        ("get", f"/api/v1/products/{product_id}/stock/history", None),
        ("post", f"/api/v1/products/{product_id}/stock/in", {"quantity": "1"}),
        ("post", f"/api/v1/products/{product_id}/stock/adjust", {"new_stock": "2"}),
    ]
    for method, path, payload in forbidden:
        response = await client.request(method, path, json=payload, headers=user_headers)
        assert response.status_code == 403, (method, path, response.text)
        assert response.json()["error"]["code"] == "PERMISSION_DENIED"

    assert (
        await client.get("/api/v1/reports/products", headers=reporter_headers)
    ).status_code == 200
    assert (await client.get("/api/v1/products", headers=reporter_headers)).status_code == 403

    current = await client.get("/api/v1/roles/reporter/permissions", headers=auth_headers)
    role = current.json()["data"]
    expanded = sorted(
        set(role["permissions"]) | {"products.view", "stock.view", "stock.history.view"}
    )
    updated = await client.put(
        "/api/v1/roles/reporter/permissions",
        headers=auth_headers,
        json={"permissions": expanded, "expected_version": role["version"]},
    )
    assert updated.status_code == 200, updated.text
    assert (await client.get("/api/v1/products", headers=reporter_headers)).status_code == 200

    conflict = await client.put(
        "/api/v1/roles/reporter/permissions",
        headers=auth_headers,
        json={"permissions": expanded, "expected_version": role["version"]},
    )
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "ROLE_PERMISSION_CONFLICT"


@pytest.mark.asyncio
async def test_logout_and_password_reset_revoke_sessions(
    client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    user = await create_user(client, auth_headers, "user", username="session_user")
    user_headers = await login(client, user["username"])
    assert (await client.get("/api/v1/auth/me", headers=user_headers)).status_code == 200
    assert (await client.post("/api/v1/auth/logout", headers=user_headers)).status_code == 200
    assert (await client.get("/api/v1/auth/me", headers=user_headers)).status_code == 401

    second_headers = await login(client, user["username"])
    reset = await client.post(
        f"/api/v1/users/{user['id']}/reset-password",
        headers=auth_headers,
        json={"password": "NewStrongPass456!"},
    )
    assert reset.status_code == 200, reset.text
    assert (await client.get("/api/v1/auth/me", headers=second_headers)).status_code == 401
    assert (
        await client.post(
            "/api/v1/auth/login",
            json={"username": user["username"], "password": "StrongPass123!"},
        )
    ).status_code == 401
    assert (
        await client.post(
            "/api/v1/auth/login",
            json={"username": user["username"], "password": "NewStrongPass456!"},
        )
    ).status_code == 200


@pytest.mark.asyncio
async def test_soft_delete_preserves_stock_ledger_and_audit(
    client: httpx.AsyncClient, auth_headers: dict[str, str], create_product
) -> None:
    product = await create_product(initial_stock="12")
    request_id = "soft-delete-test"
    deleted = await client.delete(
        f"/api/v1/products/{product['id']}",
        headers={**auth_headers, "X-Request-ID": request_id},
    )
    assert deleted.status_code == 200
    assert deleted.headers["X-Request-ID"] == request_id
    assert (
        await client.get(f"/api/v1/products/{product['id']}", headers=auth_headers)
    ).status_code == 404

    async with AsyncSessionFactory() as session:
        stored = await session.get(Product, product["id"])
        assert stored is not None and stored.deleted_at is not None
        count = await session.scalar(
            select(func.count())
            .select_from(StockTransaction)
            .where(StockTransaction.product_id == product["id"])
        )
        assert count == 1
        event = await session.scalar(
            select(AuditEvent).where(
                AuditEvent.request_id == request_id,
                AuditEvent.action == "PRODUCT_DELETED",
            )
        )
        assert event is not None
        assert event.actor_username == "admin"

    restored = await client.post(
        f"/api/v1/products/{product['id']}/restore",
        headers={**auth_headers, "X-Request-ID": "restore-test"},
    )
    assert restored.status_code == 200, restored.text
    assert restored.json()["data"]["id"] == product["id"]
    assert (
        await client.get(f"/api/v1/products/{product['id']}", headers=auth_headers)
    ).status_code == 200
    async with AsyncSessionFactory() as session:
        restored_event = await session.scalar(
            select(AuditEvent).where(
                AuditEvent.request_id == "restore-test",
                AuditEvent.action == "PRODUCT_RESTORED",
            )
        )
        assert restored_event is not None


@pytest.mark.asyncio
async def test_last_admin_and_admin_only_permissions_are_invariant(
    client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    demote = await client.put("/api/v1/users/1", headers=auth_headers, json={"role": "manager"})
    assert demote.status_code == 400
    assert demote.json()["error"]["code"] == "SELF_DEMOTION_NOT_ALLOWED"

    reporter = await client.get("/api/v1/roles/reporter/permissions", headers=auth_headers)
    role = reporter.json()["data"]
    invalid = await client.put(
        "/api/v1/roles/reporter/permissions",
        headers=auth_headers,
        json={
            "permissions": [*role["permissions"], "users.view"],
            "expected_version": role["version"],
        },
    )
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "INVALID_PERMISSION_SET"


@pytest.mark.asyncio
async def test_login_rate_limit_and_uniform_invalid_identity_response(
    client: httpx.AsyncClient,
) -> None:
    for _ in range(5):
        response = await client.post(
            "/api/v1/auth/login", json={"username": "missing", "password": "wrong"}
        )
        assert response.status_code == 401
        assert "inactive" not in response.text.lower()
    limited = await client.post(
        "/api/v1/auth/login", json={"username": "missing", "password": "wrong"}
    )
    assert limited.status_code == 429
    assert limited.json()["error"]["code"] == "AUTH_RATE_LIMITED"


def test_audit_redaction_is_recursive_and_json_safe() -> None:
    sanitized = audit_json(
        {
            "password": "secret",
            "nested": {"access_token": "token", "value": b"binary"},
            "authorization_header": "Bearer secret",
        }
    )
    assert sanitized == {
        "password": "[REDACTED]",
        "nested": {"access_token": "[REDACTED]", "value": "[BINARY REDACTED]"},
        "authorization_header": "[REDACTED]",
    }


@pytest.mark.asyncio
async def test_audit_query_separates_operational_and_security_events(
    client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    product_payload: dict,
) -> None:
    manager = await create_user(client, auth_headers, "manager", username="audit_manager")
    manager_headers = await login(client, manager["username"])
    created = await client.post("/api/v1/products", json=product_payload, headers=manager_headers)
    assert created.status_code == 201

    operational = await client.get("/api/v1/audit-events", headers=manager_headers)
    assert operational.status_code == 200
    assert operational.json()["data"]["items"]
    assert all(item["category"] != "SECURITY" for item in operational.json()["data"]["items"])
    denied_security = await client.get(
        "/api/v1/audit-events", params={"category": "SECURITY"}, headers=manager_headers
    )
    assert denied_security.status_code == 403

    security = await client.get(
        "/api/v1/audit-events", params={"category": "SECURITY"}, headers=auth_headers
    )
    assert security.status_code == 200
    assert any(item["action"] == "USER_CREATED" for item in security.json()["data"]["items"])


@pytest.mark.asyncio
async def test_last_activity_is_throttled(
    client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    sessions = await client.get("/api/v1/users/1/sessions", headers=auth_headers)
    session_id = sessions.json()["data"][0]["id"]
    old = datetime.now(UTC) - timedelta(minutes=10)
    async with AsyncSessionFactory() as session:
        user_session = await session.get(UserSession, session_id)
        user_session.last_seen_at = old
        await session.commit()

    first = await client.get("/api/v1/auth/me", headers=auth_headers)
    assert first.status_code == 200
    first_activity = first.json()["data"]["last_activity_at"]
    second = await client.get("/api/v1/auth/me", headers=auth_headers)
    assert second.status_code == 200
    assert second.json()["data"]["last_activity_at"] == first_activity
