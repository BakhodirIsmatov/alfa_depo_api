from app.seed import build_seed_request
from app.services.audit import request_id


def test_seed_request_is_starlette_and_audit_compatible() -> None:
    request = build_seed_request()

    assert request.method == "POST"
    assert request.url.scheme == "http"
    assert request.url.path == "/internal/seed"
    assert request_id(request) == "seed"
