import httpx
import pytest


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("language", "title", "local_processing_note"),
    [
        (
            "tr",
            "Gizlilik Politikası",
            "yalnızca OCR amacıyla çekilen görüntü cihaz üzerinde Google ML Kit ile işlenir",
        ),
        (
            "en",
            "Privacy Policy",
            "an image captured only for OCR in the mobile application is processed on the device",
        ),
    ],
)
async def test_privacy_policy_is_public_localized_html(
    client: httpx.AsyncClient,
    language: str,
    title: str,
    local_processing_note: str,
) -> None:
    response = await client.get(f"/api/privacy-policy/{language}")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert response.headers["content-language"] == language
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
    assert f'<html lang="{language}">' in response.text
    assert title in response.text
    assert local_processing_note in response.text
    assert "info@alfateks.com.tr" in response.text
    assert f'href="https://api-depo.xtrial.uz/api/privacy-policy/{language}"' in response.text


@pytest.mark.asyncio
async def test_privacy_policy_default_redirects_to_turkish(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/privacy-policy", follow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"] == "/api/privacy-policy/tr"
