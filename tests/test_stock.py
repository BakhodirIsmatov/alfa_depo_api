from decimal import Decimal

import httpx
import pytest


@pytest.mark.asyncio
async def test_stock_in_out_adjustment_and_history(
    client: httpx.AsyncClient, auth_headers: dict[str, str], create_product
) -> None:
    product = await create_product()
    product_id = product["id"]

    stock_in = await client.post(
        f"/api/v1/products/{product_id}/stock/in",
        json={"quantity": "5.500", "note": "Delivery"},
        headers=auth_headers,
    )
    assert stock_in.status_code == 201
    assert Decimal(stock_in.json()["data"]["new_stock"]) == Decimal("30.500")

    stock_out = await client.post(
        f"/api/v1/products/{product_id}/stock/out",
        json={"quantity": "2.500"},
        headers=auth_headers,
    )
    assert stock_out.status_code == 201
    assert Decimal(stock_out.json()["data"]["new_stock"]) == Decimal("28.000")

    adjustment = await client.post(
        f"/api/v1/products/{product_id}/stock/adjust",
        json={"new_stock": "12.000", "note": "Counted"},
        headers=auth_headers,
    )
    assert adjustment.status_code == 201
    assert Decimal(adjustment.json()["data"]["previous_stock"]) == Decimal("28.000")
    assert Decimal(adjustment.json()["data"]["new_stock"]) == Decimal("12.000")

    history = await client.get(f"/api/v1/products/{product_id}/stock/history", headers=auth_headers)
    assert history.status_code == 200
    items = history.json()["data"]["items"]
    assert [item["transaction_type"] for item in items] == ["ADJUSTMENT", "OUT", "IN", "IN"]


@pytest.mark.asyncio
async def test_negative_stock_prevention(
    client: httpx.AsyncClient, auth_headers: dict[str, str], create_product
) -> None:
    product = await create_product(initial_stock="3.000")
    response = await client.post(
        f"/api/v1/products/{product['id']}/stock/out",
        json={"quantity": "4.000"},
        headers=auth_headers,
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INSUFFICIENT_STOCK"

    stock = await client.get(f"/api/v1/products/{product['id']}/stock", headers=auth_headers)
    assert Decimal(stock.json()["data"]["current_stock"]) == Decimal("3.000")


@pytest.mark.asyncio
async def test_stock_quantities_must_be_positive(
    client: httpx.AsyncClient, auth_headers: dict[str, str], create_product
) -> None:
    product = await create_product()
    response = await client.post(
        f"/api/v1/products/{product['id']}/stock/in",
        json={"quantity": 0},
        headers=auth_headers,
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
