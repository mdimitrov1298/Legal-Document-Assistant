"""Document upload validation, listing and deletion."""

from __future__ import annotations

import hashlib

from tests.api.helpers import API, CONTRACT_TEXT, create_case, ingest, upload


def test_upload_returns_sha256_and_lists(client):
    case_id = create_case(client)
    r = upload(client, case_id)
    assert r.status_code == 201
    doc = r.json()
    assert doc["sha256"] == hashlib.sha256(CONTRACT_TEXT.encode()).hexdigest()
    assert doc["size_bytes"] == len(CONTRACT_TEXT.encode())
    assert doc["content_type"] == "text/plain"

    listed = client.get(f"{API}/cases/{case_id}/documents").json()
    assert [d["id"] for d in listed] == [doc["id"]]
    assert client.get(f"{API}/cases/{case_id}").json()["document_count"] == 1


def test_octet_stream_accepted_when_suffix_ok(client):
    case_id = create_case(client)
    r = upload(client, case_id, content_type="application/octet-stream")
    assert r.status_code == 201
    assert r.json()["content_type"] == "text/plain"


def test_pdf_upload_requires_pdf_header(client):
    case_id = create_case(client)
    r = upload(client, case_id, "a.pdf", b"not a pdf", "application/pdf")
    assert r.status_code == 415
    r = upload(client, case_id, "a.pdf", b"%PDF-1.4\n%fake", "application/pdf")
    assert r.status_code == 201
    assert r.json()["content_type"] == "application/pdf"


def test_unsupported_suffix_is_415(client):
    case_id = create_case(client)
    r = upload(client, case_id, "notes.docx", b"data", "application/msword")
    assert r.status_code == 415
    assert r.json()["error"]["code"] == "unsupported_media_type"


def test_mismatched_content_type_is_415(client):
    case_id = create_case(client)
    r = upload(client, case_id, "a.txt", b"text", "image/png")
    assert r.status_code == 415


def test_empty_file_is_400(client):
    case_id = create_case(client)
    r = upload(client, case_id, data=b"")
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "empty_file"


def test_too_large_is_413(client, monkeypatch):
    from app.core.config import clear_settings_cache

    monkeypatch.setenv("MAX_UPLOAD_MB", "1")
    clear_settings_cache()
    case_id = create_case(client)
    r = upload(client, case_id, data=b"a" * (1024 * 1024 + 1))
    assert r.status_code == 413
    body = r.json()
    assert body["error"]["code"] == "payload_too_large"
    assert body["error"]["details"]["max_upload_mb"] == 1


def test_upload_to_missing_case_is_404(client):
    r = upload(client, "missing")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "case_not_found"


def test_delete_document(client, isolated_env):
    case_id = create_case(client)
    doc_id = upload(client, case_id).json()["id"]
    ingest(client, case_id)
    r = client.delete(f"{API}/cases/{case_id}/documents/{doc_id}")
    assert r.status_code == 204
    assert client.get(f"{API}/cases/{case_id}/documents").json() == []
    assert list((isolated_env / "uploads" / case_id).glob("*")) == []

    r = client.delete(f"{API}/cases/{case_id}/documents/{doc_id}")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "document_not_found"


def test_delete_document_removes_its_chunks(client):
    from app.services.vector_store import get_vectorstore

    case_id = create_case(client)
    doc1 = upload(client, case_id, "a.txt").json()["id"]
    upload(client, case_id, "b.txt", "Втори документ по делото.".encode())
    ingest(client, case_id)
    before = get_vectorstore().count(case_id)
    client.delete(f"{API}/cases/{case_id}/documents/{doc1}")
    case = client.get(f"{API}/cases/{case_id}").json()
    assert case["status"] == "stale"
    assert 0 < case["chunk_count"] < before
    assert get_vectorstore().count(case_id) == case["chunk_count"]
