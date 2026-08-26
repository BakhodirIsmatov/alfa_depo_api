from io import BytesIO

import httpx
import pytest
from PIL import Image


def image_bytes(color: str = "white") -> bytes:
    output = BytesIO()
    Image.new("RGB", (640, 480), color).save(output, format="JPEG")
    return output.getvalue()


@pytest.mark.asyncio
async def test_product_create_read_update_and_delete(
    client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    product_payload: dict,
) -> None:
    created_response = await client.post(
        "/api/v1/products", json=product_payload, headers=auth_headers
    )
    assert created_response.status_code == 201
    created = created_response.json()["data"]
    assert created["product_code"] == product_payload["product_code"]
    assert created["qr_code"] == product_payload["product_code"]
    assert created["barcode"] == product_payload["product_code"]
    assert created["unit"] == "kg"
    assert created["current_stock"] == "25.000"

    read = await client.get(f"/api/v1/products/{created['id']}", headers=auth_headers)
    assert read.status_code == 200
    assert read.json()["data"]["name"] == product_payload["name"]

    updated = await client.put(
        f"/api/v1/products/{created['id']}",
        json={"name": "Updated Cotton", "brand": None},
        headers=auth_headers,
    )
    assert updated.status_code == 200
    assert updated.json()["data"]["name"] == "Updated Cotton"
    assert updated.json()["data"]["brand"] is None

    deleted = await client.delete(f"/api/v1/products/{created['id']}", headers=auth_headers)
    assert deleted.status_code == 200
    missing = await client.get(f"/api/v1/products/{created['id']}", headers=auth_headers)
    assert missing.status_code == 404


@pytest.mark.asyncio
async def test_product_label_templates_are_exposed(
    client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    response = await client.get("/api/v1/products/label-templates", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()["data"]
    assert [item["code"] for item in data] == [
        "barcode-30x20",
        "barcode-40x30",
        "qr-30x30",
        "qr-40x40",
    ]
    assert data[0]["kind"] == "barcode"
    assert data[2]["kind"] == "qr"


@pytest.mark.asyncio
async def test_product_search_and_lookup(
    client: httpx.AsyncClient, auth_headers: dict[str, str], create_product
) -> None:
    product = await create_product()
    search = await client.get(
        "/api/v1/products?search=LOT-001&sort_by=name&sort_order=asc",
        headers=auth_headers,
    )
    assert search.status_code == 200
    assert search.json()["data"]["pagination"]["total"] == 1

    for identifier in (product["product_code"], product["qr_code"], product["barcode"]):
        response = await client.get(f"/api/v1/products/lookup/{identifier}", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["data"]["id"] == product["id"]


@pytest.mark.asyncio
async def test_backend_derives_identifiers_from_product_code(
    client: httpx.AsyncClient, auth_headers: dict[str, str], product_payload: dict
) -> None:
    response = await client.post(
        "/api/v1/products",
        json={**product_payload, "product_code": "MANUAL-CODE-42", "qr_code": "CLIENT-QR", "barcode": "CLIENT-BARCODE"},
        headers=auth_headers,
    )
    assert response.status_code == 201
    data = response.json()["data"]
    assert data["product_code"] == "MANUAL-CODE-42"
    assert data["product_code"] == data["qr_code"] == data["barcode"]


@pytest.mark.asyncio
async def test_blank_required_product_name_is_rejected(
    client: httpx.AsyncClient, auth_headers: dict[str, str], product_payload: dict
) -> None:
    response = await client.post(
        "/api/v1/products",
        json={**product_payload, "name": "   "},
        headers=auth_headers,
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_optional_product_fields_and_kg_only_are_enforced(
    client: httpx.AsyncClient, auth_headers: dict[str, str], product_payload: dict
) -> None:
    missing_optional_fields = await client.post(
        "/api/v1/products",
        json={
            key: value
            for key, value in product_payload.items()
            if key not in {"brand", "description", "color", "color_code"}
        },
        headers=auth_headers,
    )
    assert missing_optional_fields.status_code == 201
    meter = await client.post(
        "/api/v1/products", json={**product_payload, "unit": "meter"}, headers=auth_headers
    )
    assert meter.status_code == 422


@pytest.mark.asyncio
async def test_optional_product_fields_can_be_cleared_on_update(
    client: httpx.AsyncClient, auth_headers: dict[str, str], create_product
) -> None:
    product = await create_product()
    cleared = await client.put(
        f"/api/v1/products/{product['id']}",
        json={"description": None},
        headers=auth_headers,
    )
    assert cleared.status_code == 200
    assert cleared.json()["data"]["description"] is None


@pytest.mark.asyncio
async def test_product_image_upload_and_remove(
    client: httpx.AsyncClient, auth_headers: dict[str, str], create_product, tmp_path, monkeypatch
) -> None:
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "media_root", tmp_path)
    product = await create_product()
    upload = await client.post(
        f"/api/v1/products/{product['id']}/image",
        files={"image": ("label.jpg", image_bytes(), "image/jpeg")},
        headers=auth_headers,
    )
    assert upload.status_code == 200
    assert upload.json()["data"]["image_url"].startswith("/media/products/")
    stored = list((tmp_path / "products").glob("*.webp"))
    assert len(stored) == 1
    with Image.open(stored[0]) as normalized:
        assert normalized.format == "WEBP"

    replacement = await client.post(
        f"/api/v1/products/{product['id']}/image",
        files={"image": ("replacement.png", image_bytes("blue"), "image/png")},
        headers=auth_headers,
    )
    assert replacement.status_code == 200
    assert len(list((tmp_path / "products").glob("*.webp"))) == 1
    removed = await client.delete(f"/api/v1/products/{product['id']}/image", headers=auth_headers)
    assert removed.status_code == 200
    assert removed.json()["data"]["image_url"] is None
    assert list((tmp_path / "products").glob("*.webp")) == []


@pytest.mark.asyncio
async def test_product_image_accepts_camera_upload_without_specific_mime(
    client: httpx.AsyncClient, auth_headers: dict[str, str], create_product, tmp_path, monkeypatch
) -> None:
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "media_root", tmp_path)
    product = await create_product()
    response = await client.post(
        f"/api/v1/products/{product['id']}/image",
        files={"image": ("camera.jpg", image_bytes(), "application/octet-stream")},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["data"]["image_url"].startswith("/media/products/")


@pytest.mark.asyncio
async def test_product_image_rejects_spoofed_content(
    client: httpx.AsyncClient, auth_headers: dict[str, str], create_product
) -> None:
    product = await create_product()
    response = await client.post(
        f"/api/v1/products/{product['id']}/image",
        files={"image": ("fake.jpg", b"not-an-image", "image/jpeg")},
        headers=auth_headers,
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_IMAGE"


@pytest.mark.asyncio
async def test_ocr_endpoint_returns_editable_suggestions(
    client: httpx.AsyncClient, auth_headers: dict[str, str], monkeypatch
) -> None:
    from app.api import products as products_api
    from app.services.ocr import parse_product_text

    monkeypatch.setattr(
        products_api,
        "extract_product_fields",
        lambda *_args, **_kwargs: parse_product_text(
            "Product: Premium Poplin\nLot No: LOT-42\nBrand: Alfateks\n"
            "Description: Premium weave\nQuantity: 25.5 kg\nMinimum: 4 kg"
        ),
    )
    response = await client.post(
        "/api/v1/products/ocr/extract",
        files={"image": ("label.jpg", image_bytes(), "image/jpeg")},
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["fields"]["name"] == "Premium Poplin"
    assert data["fields"]["lot_number"] == "LOT-42"
    assert data["fields"]["brand"] == "Alfateks"
    assert data["fields"]["description"] == "Premium weave"
    assert data["fields"]["initial_stock"] == "25.5"
    assert data["fields"]["unit"] == "kg"


def test_ocr_parser_does_not_persist_or_invent_missing_fields() -> None:
    from app.services.ocr import parse_product_text

    result = parse_product_text("Brand: Alfateks\nLot: L-100")
    assert result.fields.brand == "Alfateks"
    assert result.fields.lot_number == "L-100"
    assert result.fields.description is None
    assert result.warnings


def test_seed_products_follow_product_contract() -> None:
    from app.seed import SAMPLE_PRODUCTS

    assert len(SAMPLE_PRODUCTS) == 5
    assert all(product.unit == "kg" for product in SAMPLE_PRODUCTS)
    assert all(product.description for product in SAMPLE_PRODUCTS)
