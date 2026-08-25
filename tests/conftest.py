import os
from collections.abc import AsyncIterator

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["JWT_SECRET_KEY"] = "test-secret-key-that-is-at-least-32-characters"
os.environ["DEBUG"] = "true"
os.environ["ALLOW_NEGATIVE_STOCK"] = "false"

import httpx
import pytest

from app.core.database import AsyncSessionFactory, Base, engine
from app.core.permissions import UserRole
from app.core.security import hash_password
from app.main import app
from app.models.user import User
from app.repositories.access import sync_access_catalog


@pytest.fixture(autouse=True)
async def reset_database() -> AsyncIterator[None]:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)
    async with AsyncSessionFactory() as session:
        roles = await sync_access_catalog(session)
        session.add(
            User(
                username="admin",
                email="admin@example.com",
                full_name="Test Administrator",
                password_hash=hash_password("AdminPass123!"),
                is_active=True,
                is_admin=True,
                role_id=roles[UserRole.ADMIN].id,
            )
        )
        await session.commit()
    yield


@pytest.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as test_client:
        yield test_client


@pytest.fixture
async def auth_headers(client: httpx.AsyncClient) -> dict[str, str]:
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "AdminPass123!"},
    )
    token = response.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def product_payload() -> dict:
    return {
        "name": "Premium Cotton Poplin",
        "description": "Fine woven textile",
        "lot_number": "LOT-001",
        "brand": "ALFATEKS",
        "color": "White",
        "color_code": "#FFFFFF",
        "unit": "kg",
        "minimum_stock": "10.000",
        "initial_stock": "25.000",
    }


@pytest.fixture
def create_product(client: httpx.AsyncClient, auth_headers: dict[str, str], product_payload: dict):
    async def _create(**overrides):
        payload = {**product_payload, **overrides}
        response = await client.post("/api/v1/products", json=payload, headers=auth_headers)
        assert response.status_code == 201, response.text
        return response.json()["data"]

    return _create
