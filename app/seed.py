import asyncio
import os

from sqlalchemy import select
from starlette.requests import Request

from app.core.database import AsyncSessionFactory
from app.core.permissions import UserRole
from app.core.security import hash_password, verify_password
from app.models.product import Product
from app.models.user import User
from app.repositories.access import sync_access_catalog
from app.schemas.product import ProductCreate
from app.services.product import ProductService

SAMPLE_PRODUCTS = [
    ProductCreate(
        product_code="ALF-POPLIN-001",
        name="Premium Cotton Poplin",
        lot_number="LOT-2026-0820",
        brand="Alfateks",
        description="Lightweight premium cotton poplin fabric",
        initial_stock="500",
        minimum_stock="100",
    ),
    ProductCreate(
        product_code="ALF-POLY-001",
        name="Polyester Fabric",
        lot_number="LOT-2026-0819",
        brand="Alfateks",
        description="Durable navy polyester fabric",
        initial_stock="350",
        minimum_stock="75",
    ),
    ProductCreate(
        product_code="ALF-DENIM-001",
        name="Denim 12 oz",
        lot_number="LOT-2026-0818",
        brand="Alfateks",
        description="Heavyweight 12 oz indigo denim",
        initial_stock="220",
        minimum_stock="50",
    ),
    ProductCreate(
        product_code="ALF-GABARDINE-001",
        name="Gabardine Fabric",
        lot_number="LOT-2026-0817",
        brand="Alfateks",
        description="Dense black gabardine fabric",
        initial_stock="180",
        minimum_stock="40",
    ),
    ProductCreate(
        product_code="ALF-JERSEY-001",
        name="Jersey Fabric",
        lot_number="LOT-2026-0816",
        brand="Alfateks",
        description="Soft grey jersey fabric",
        initial_stock="300",
        minimum_stock="60",
    ),
]


def build_seed_request() -> Request:
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/internal/seed",
            "headers": [],
            "client": ("127.0.0.1", 0),
            "scheme": "http",
            "server": ("seed", 80),
            "query_string": b"",
            "root_path": "",
        }
    )
    request.state.request_id = "seed"
    return request


async def seed() -> None:
    password = os.getenv("SEED_ADMIN_PASSWORD")
    if not password or len(password) < 8 or password.startswith("replace-with"):
        raise RuntimeError(
            "Set SEED_ADMIN_PASSWORD to a non-placeholder value of at least 8 characters"
        )
    username = os.getenv("SEED_ADMIN_USERNAME", "admin").strip().lower()
    email = os.getenv("SEED_ADMIN_EMAIL", "admin@example.com").strip().lower()
    full_name = os.getenv("SEED_ADMIN_FULL_NAME", "Warehouse Administrator").strip()

    async with AsyncSessionFactory() as session:
        roles = await sync_access_catalog(session)
        admin_role = roles[UserRole.ADMIN]
        matches = list(
            (
                await session.scalars(
                    select(User).where((User.username == username) | (User.email == email))
                )
            ).all()
        )
        if len(matches) > 1:
            raise RuntimeError(
                "Seed username and email belong to different users; resolve the conflict first"
            )
        admin = matches[0] if matches else None
        if admin is None:
            admin = User(
                username=username,
                email=email,
                full_name=full_name,
                password_hash=hash_password(password),
                is_active=True,
                is_admin=True,
                role_id=admin_role.id,
                role=admin_role,
            )
            session.add(admin)
            await session.commit()
            await session.refresh(admin)
            print(f"Created admin user: {username}")
        elif admin.role_id != admin_role.id:
            raise RuntimeError("Existing seed identity is not an administrator")
        else:
            changed = False
            desired_values = {
                "username": username,
                "email": email,
                "full_name": full_name,
                "is_active": True,
                "is_admin": True,
                "role_id": admin_role.id,
            }
            for field, value in desired_values.items():
                if getattr(admin, field) != value:
                    setattr(admin, field, value)
                    changed = True
            if not verify_password(password, admin.password_hash):
                admin.password_hash = hash_password(password)
                changed = True
            if changed:
                await session.commit()
                await session.refresh(admin)
                print(f"Updated admin user: {username}")
            else:
                print(f"Admin user is up to date: {username}")

        product_service = ProductService(session)
        seed_request = build_seed_request()
        for payload in SAMPLE_PRODUCTS:
            exists = await session.scalar(select(Product.id).where(Product.name == payload.name))
            if exists is None:
                product = await product_service.create(payload, admin, seed_request)
                print(f"Created product: {product.product_code} {product.name}")
            else:
                print(f"Product already exists: {payload.name}")


if __name__ == "__main__":
    asyncio.run(seed())
