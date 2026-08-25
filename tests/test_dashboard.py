from decimal import Decimal

import httpx
import pytest


@pytest.mark.asyncio
async def test_dashboard_statistics_low_and_out_of_stock(
    client: httpx.AsyncClient, auth_headers: dict[str, str], create_product
) -> None:
    await create_product(
        name="Healthy Stock", lot_number="LOT-H", initial_stock="50", minimum_stock="10"
    )
    await create_product(
        name="Low Stock", lot_number="LOT-L", initial_stock="5", minimum_stock="10"
    )
    await create_product(
        name="Out of Stock", lot_number="LOT-O", initial_stock="0", minimum_stock="10"
    )

    response = await client.get("/api/v1/dashboard", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["total_products"] == 3
    assert Decimal(data["total_stock"]) == Decimal("55")
    assert data["low_stock_products"] == 2
    assert data["out_of_stock_products"] == 1
    assert len(data["recent_products"]) == 3
    assert len(data["recent_stock_transactions"]) == 2
