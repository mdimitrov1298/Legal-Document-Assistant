"""X-Request-ID propagation, access log and log formatting."""

from __future__ import annotations

import json
import logging
import uuid

from app.core.logging import JsonFormatter, RequestIdFilter, request_id_var


def test_request_id_is_generated(client):
    r = client.get("/")
    rid = r.headers["X-Request-ID"]
    assert str(uuid.UUID(rid)) == rid


def test_incoming_request_id_is_echoed(client):
    r = client.get("/", headers={"X-Request-ID": "abc-123"})
    assert r.headers["X-Request-ID"] == "abc-123"


def test_invalid_incoming_request_id_is_replaced(client):
    r = client.get("/", headers={"X-Request-ID": "bad id with spaces"})
    assert r.headers["X-Request-ID"] != "bad id with spaces"
    uuid.UUID(r.headers["X-Request-ID"])


def test_access_log_has_duration_and_status(client, caplog):
    with caplog.at_level(logging.INFO, logger="app.access"):
        client.get("/", headers={"X-Request-ID": "log-1"})
    records = [r for r in caplog.records if r.name == "app.access"]
    assert records
    rec = records[-1]
    assert rec.status == 200
    assert rec.path == "/"
    assert rec.duration_ms >= 0


def test_json_formatter_includes_request_id_and_extras():
    token = request_id_var.set("json-rid")
    try:
        record = logging.LogRecord(
            "app.test", logging.INFO, __file__, 1, "hi %s", ("x",), None
        )
        record.status = 201
        RequestIdFilter().filter(record)
        payload = json.loads(JsonFormatter().format(record))
    finally:
        request_id_var.reset(token)
    assert payload["message"] == "hi x"
    assert payload["request_id"] == "json-rid"
    assert payload["status"] == 201
    assert payload["level"] == "INFO"
