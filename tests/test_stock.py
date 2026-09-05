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
        json={"quantity": "5.500", "count": 6, "note": "Delivery"},
        headers=auth_headers,
    )
    assert stock_in.status_code == 201
    assert Decimal(stock_in.json()["data"]["new_stock"]) == Decimal("30.500")
    assert stock_in.json()["data"]["previous_count"] is None
    assert stock_in.json()["data"]["count"] == 6
    assert stock_in.json()["data"]["new_count"] == 6

    stock_out = await client.post(
        f"/api/v1/products/{product_id}/stock/out",
        json={"quantity": "2.500", "count": 2},
        headers=auth_headers,
    )
    assert stock_out.status_code == 201
    assert Decimal(stock_out.json()["data"]["new_stock"]) == Decimal("28.000")
    assert stock_out.json()["data"]["previous_count"] == 6
    assert stock_out.json()["data"]["new_count"] == 4

    adjustment = await client.post(
        f"/api/v1/products/{product_id}/stock/adjust",
        json={"quantity": "12.000", "count": 3, "note": "Counted"},
        headers=auth_headers,
    )
    assert adjustment.status_code == 201
    assert Decimal(adjustment.json()["data"]["previous_stock"]) == Decimal("28.000")
    assert Decimal(adjustment.json()["data"]["quantity"]) == Decimal("12.000")
    assert Decimal(adjustment.json()["data"]["new_stock"]) == Decimal("40.000")
    assert adjustment.json()["data"]["previous_count"] == 4
    assert adjustment.json()["data"]["new_count"] == 7

    stock = await client.get(f"/api/v1/products/{product_id}/stock", headers=auth_headers)
    assert stock.status_code == 200
    assert stock.json()["data"]["count"] == 7

    history = await client.get(f"/api/v1/products/{product_id}/stock/history", headers=auth_headers)
    assert history.status_code == 200
    items = history.json()["data"]["items"]
    assert [item["transaction_type"] for item in items] == ["ADJUSTMENT", "OUT", "IN", "IN"]
    assert [(item["count"], item["previous_count"], item["new_count"]) for item in items[:3]] == [
        (3, 4, 7),
        (2, 6, 4),
        (6, None, 6),
    ]


@pytest.mark.asyncio
async def test_negative_stock_prevention(
    client: httpx.AsyncClient, auth_headers: dict[str, str], create_product
) -> None:
    product = await create_product(initial_stock="3.000")
    response = await client.post(
        f"/api/v1/products/{product['id']}/stock/out",
        json={"quantity": "4.000", "count": 1},
        headers=auth_headers,
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INSUFFICIENT_STOCK"

    stock = await client.get(f"/api/v1/products/{product['id']}/stock", headers=auth_headers)
    assert Decimal(stock.json()["data"]["current_stock"]) == Decimal("3.000")


@pytest.mark.asyncio
async def test_stock_quantity_and_count_validation(
    client: httpx.AsyncClient, auth_headers: dict[str, str], create_product
) -> None:
    product = await create_product()
    response = await client.post(
        f"/api/v1/products/{product['id']}/stock/in",
        json={"quantity": 0, "count": 1},
        headers=auth_headers,
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"

    missing_count = await client.post(
        f"/api/v1/products/{product['id']}/stock/in",
        json={"quantity": 1},
        headers=auth_headers,
    )
    assert missing_count.status_code == 422
    assert missing_count.json()["error"]["code"] == "VALIDATION_ERROR"

    zero_count = await client.post(
        f"/api/v1/products/{product['id']}/stock/in",
        json={"quantity": 1, "count": 0},
        headers=auth_headers,
    )
    assert zero_count.status_code == 422
    assert zero_count.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_stock_out_prevents_negative_product_count(
    client: httpx.AsyncClient, auth_headers: dict[str, str], create_product
) -> None:
    product = await create_product(initial_stock="10.000", count=2)
    response = await client.post(
        f"/api/v1/products/{product['id']}/stock/out",
        json={"quantity": "1.000", "count": 3},
        headers=auth_headers,
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INSUFFICIENT_PRODUCT_COUNT"

    stock = await client.get(f"/api/v1/products/{product['id']}/stock", headers=auth_headers)
    assert stock.json()["data"]["count"] == 2
    assert Decimal(stock.json()["data"]["current_stock"]) == Decimal("10.000")
