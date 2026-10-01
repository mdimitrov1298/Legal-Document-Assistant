"""Every non-2xx response uses the error envelope."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.errors import NoDocumentsError
from app.main import create_app


def _assert_envelope(response, status: int, code: str) -> dict:
    assert response.status_code == status
    body = response.json()
    assert set(body) == {"error", "request_id"}
    assert body["error"]["code"] == code
    assert isinstance(body["error"]["message"], str) and body["error"]["message"]
    assert "details" in body["error"]
    assert body["request_id"] == response.headers["X-Request-ID"]
    return body


def test_unknown_route_returns_not_found_envelope(client):
    _assert_envelope(client.get("/does-not-exist"), 404, "not_found")


def test_method_not_allowed_envelope(client):
    _assert_envelope(client.delete("/"), 405, "method_not_allowed")


def test_validation_error_envelope_lists_fields(client):
    body = _assert_envelope(
        client.post("/api/v1/cases", json={}), 422, "validation_error"
    )
    locs = [e["loc"] for e in body["error"]["details"]["errors"]]
    assert ["body", "title"] in locs


def test_app_error_envelope():
    app = create_app()

    @app.get("/raise-app-error")
    async def raise_app_error():
        raise NoDocumentsError(details={"case_id": "x"})

    with TestClient(app) as c:
        body = _assert_envelope(c.get("/raise-app-error"), 409, "no_documents")
    assert body["error"]["details"] == {"case_id": "x"}


def test_unhandled_exception_becomes_internal_error():
    app = create_app()

    @app.get("/boom")
    async def boom():
        raise RuntimeError("secret internals")

    with TestClient(app, raise_server_exceptions=False) as c:
        r = c.get("/boom", headers={"X-Request-ID": "req-boom-1"})
    body = _assert_envelope(r, 500, "internal_error")
    assert body["request_id"] == "req-boom-1"
    assert "secret" not in body["error"]["message"]
