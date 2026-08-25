from decimal import Decimal

import httpx
import pytest


@pytest.mark.asyncio
async def test_product_report_filters_summary_and_options(
    client: httpx.AsyncClient, auth_headers: dict[str, str], create_product
) -> None:
    await create_product(
        name="Healthy Navy",
        lot_number="REPORT-H",
        brand="Report Brand A",
        color="Navy",
        initial_stock="50",
        minimum_stock="10",
    )
    await create_product(
        name="Low Navy",
        lot_number="REPORT-L",
        brand="Report Brand A",
        color="Navy",
        initial_stock="5",
        minimum_stock="10",
    )
    await create_product(
        name="Empty Black",
        lot_number="REPORT-O",
        brand="Report Brand B",
        color="Black",
        initial_stock="0",
        minimum_stock="10",
    )

    all_report = await client.get(
        "/api/v1/reports/products?page_size=2&sort_by=name&sort_order=asc",
        headers=auth_headers,
    )
    assert all_report.status_code == 200
    data = all_report.json()["data"]
    assert data["pagination"] == {
        "page": 1,
        "page_size": 2,
        "total": 3,
        "pages": 2,
    }
    assert data["summary"]["total_products"] == 3
    assert Decimal(data["summary"]["total_current_stock"]) == Decimal("55")
    assert data["summary"]["low_stock_products"] == 2
    assert data["summary"]["out_of_stock_products"] == 1

    low_report = await client.get(
        "/api/v1/reports/products?brand=Report%20Brand%20A&stock_status=low",
        headers=auth_headers,
    )
    assert low_report.status_code == 200
    low_data = low_report.json()["data"]
    assert [item["name"] for item in low_data["items"]] == ["Low Navy"]
    assert low_data["items"][0]["stock_status"] == "low"

    options = await client.get("/api/v1/reports/products/filter-options", headers=auth_headers)
    assert options.status_code == 200
    assert options.json()["data"] == {
        "brands": ["Report Brand A", "Report Brand B"],
        "colors": ["Black", "Navy"],
    }


@pytest.mark.asyncio
async def test_product_report_rejects_invalid_ranges(
    client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    response = await client.get(
        "/api/v1/reports/products?minimum_current_stock=20&maximum_current_stock=10",
        headers=auth_headers,
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_REPORT_FILTERS"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("report_format", "content_type", "signature"),
    [
        ("pdf", "application/pdf", b"%PDF"),
        ("png", "image/png", b"\x89PNG"),
        (
            "xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            b"PK",
        ),
        (
            "xls",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            b"PK",
        ),
    ],
)
async def test_product_report_exports_real_files(
    report_format: str,
    content_type: str,
    signature: bytes,
    client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    create_product,
) -> None:
    await create_product(name="Export Product", lot_number="EXPORT-1")
    response = await client.get(
        f"/api/v1/reports/products/export?format={report_format}&language=uz",
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith(content_type)
    assert response.headers["content-disposition"].endswith(
        f'.{"xlsx" if report_format in {"xls", "xlsx"} else report_format}"'
    )
    assert response.headers["x-report-row-count"] == "1"
    assert response.content.startswith(signature)


@pytest.mark.asyncio
async def test_png_export_limit_is_enforced(
    client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    create_product,
    monkeypatch,
) -> None:
    from app.core.config import get_settings

    await create_product(name="PNG One", lot_number="PNG-1")
    await create_product(name="PNG Two", lot_number="PNG-2")
    monkeypatch.setattr(get_settings(), "report_png_max_rows", 1)
    response = await client.get("/api/v1/reports/products/export?format=png", headers=auth_headers)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "REPORT_TOO_LARGE"


@pytest.mark.asyncio
async def test_daily_dashboard_report_calculates_in_out_and_adjustments(
    client: httpx.AsyncClient, auth_headers: dict[str, str], create_product
) -> None:
    product = await create_product(name="Daily Movement", lot_number="DAILY-1", initial_stock="0")
    stock_in = await client.post(
        f"/api/v1/products/{product['id']}/stock/in",
        json={"quantity": "10", "note": "daily receive"},
        headers=auth_headers,
    )
    stock_out = await client.post(
        f"/api/v1/products/{product['id']}/stock/out",
        json={"quantity": "3", "note": "daily issue"},
        headers=auth_headers,
    )
    adjustment = await client.post(
        f"/api/v1/products/{product['id']}/stock/adjust",
        json={"new_stock": "12", "note": "count"},
        headers=auth_headers,
    )
    assert stock_in.status_code == stock_out.status_code == adjustment.status_code == 201

    response = await client.get("/api/v1/dashboard/daily", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()["data"]
    summary = data["summary"]
    assert Decimal(summary["stock_in"]) == Decimal("10")
    assert Decimal(summary["stock_out"]) == Decimal("3")
    assert Decimal(summary["adjustment_in"]) == Decimal("5")
    assert Decimal(summary["adjustment_out"]) == Decimal("0")
    assert Decimal(summary["net_change"]) == Decimal("12")
    assert summary["transaction_count"] == 3
    assert summary["affected_products"] == 1
    movement = data["products"][0]
    assert Decimal(movement["opening_stock"]) == Decimal("0")
    assert Decimal(movement["closing_stock"]) == Decimal("12")

    exported = await client.get(
        f"/api/v1/dashboard/daily/export?date={data['report_date']}&format=xlsx",
        headers=auth_headers,
    )
    assert exported.status_code == 200
    assert exported.content.startswith(b"PK")


@pytest.mark.asyncio
async def test_reports_require_authentication(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/v1/reports/products")
    assert response.status_code == 401
