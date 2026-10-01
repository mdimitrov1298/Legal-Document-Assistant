"""RAG endpoints with hash_stub embeddings and a mocked Ollama."""

from __future__ import annotations

import json

import httpx

from tests.api.helpers import API, create_case, ingest, upload


def test_full_flow_stubbed(client):
    case_id = create_case(client)
    assert upload(client, case_id).status_code == 201

    result = ingest(client, case_id)
    assert result["documents_processed"] == 1
    assert result["chunks_indexed"] >= 1
    assert result["embedding_backend"] == "hash_stub"
    assert result["chunk_size"] == 800
    assert result["chunk_overlap"] == 120
    assert result["persisted"] is True
    assert result["duration_ms"] >= 0
    assert result["vector_store_path"].endswith("chroma")

    r = client.post(f"{API}/cases/{case_id}/summarize", json={"top_k": 3})
    assert r.status_code == 200
    summary = r.json()
    assert summary["stubbed"] is True
    assert summary["citations"]
    assert all(c["verbatim"] is True for c in summary["citations"])
    assert summary["citations"][0]["chunk_index"] == 0
    assert summary["chunks_used"] >= 1
    assert summary["duration_ms"] >= 0

    r = client.post(
        f"{API}/cases/{case_id}/verify",
        json={"claim": "Възнаграждението е 4500 лв."},
    )
    assert r.status_code == 200
    verify = r.json()
    assert verify["stubbed"] is True
    assert verify["verdict"] == "inconclusive"
    assert verify["retrieved_quotes"]
    assert verify["duration_ms"] >= 0


def test_summarize_without_body_uses_default_top_k(client):
    case_id = create_case(client)
    upload(client, case_id)
    ingest(client, case_id)
    r = client.post(f"{API}/cases/{case_id}/summarize")
    assert r.status_code == 200


def test_ingest_without_documents_is_409(client):
    case_id = create_case(client)
    r = client.post(f"{API}/cases/{case_id}/ingest")
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "no_documents"


def test_summarize_and_verify_require_ingest(client):
    case_id = create_case(client)
    upload(client, case_id)
    r = client.post(f"{API}/cases/{case_id}/summarize", json={})
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "case_not_ingested"
    assert r.json()["error"]["details"]["status"] == "uploaded"
    r = client.post(f"{API}/cases/{case_id}/verify", json={"claim": "Нещо"})
    assert r.json()["error"]["code"] == "case_not_ingested"


def test_stale_case_can_still_be_queried(client):
    case_id = create_case(client)
    upload(client, case_id)
    ingest(client, case_id)
    upload(client, case_id, name="b.txt", data="Допълнение.".encode())
    r = client.post(f"{API}/cases/{case_id}/verify", json={"claim": "Нещо"})
    assert r.status_code == 200


def test_reingest_rebuilds_collection(client):
    case_id = create_case(client)
    upload(client, case_id)
    first = ingest(client, case_id)
    second = ingest(client, case_id)
    assert first["chunks_indexed"] == second["chunks_indexed"]
    stats = client.get(f"{API}/cases/{case_id}/index").json()
    assert stats["chunk_count"] == second["chunks_indexed"]


def test_index_stats(client):
    case_id = create_case(client)
    stats = client.get(f"{API}/cases/{case_id}/index").json()
    assert stats["chunk_count"] == 0
    assert stats["ingested_at"] is None
    assert stats["collection"] == "case_" + case_id.replace("-", "")

    upload(client, case_id)
    ingest(client, case_id)
    stats = client.get(f"{API}/cases/{case_id}/index").json()
    assert stats["chunk_count"] >= 1
    assert stats["embedding_backend"] == "hash_stub"
    assert stats["embedding_model"] == "hash_stub"
    assert stats["ingested_at"] is not None
    assert client.get(f"{API}/cases/nope/index").status_code == 404


def test_verify_with_model_response(client, install_llm):
    payload = {
        "verdict": "supported",
        "rationale": "Цитат [0] посочва 4500 лв.",
        "supporting_quote_indices": [0],
        "denying_quote_indices": [],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["options"]["temperature"] == 0.0
        return httpx.Response(200, json={"response": json.dumps(payload)})

    install_llm(handler)
    case_id = create_case(client)
    upload(client, case_id)
    ingest(client, case_id)
    r = client.post(
        f"{API}/cases/{case_id}/verify", json={"claim": "Възнаграждението е 4500 лв."}
    )
    body = r.json()
    assert body["stubbed"] is False
    assert body["verdict"] == "supported"
    assert body["supporting_quotes"][0]["document_filename"] == "dogovor.txt"


def test_llm_unavailable_when_stub_disabled(client, install_llm):
    def down(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down", request=request)

    install_llm(down, ollama_stub_on_unavailable=False)
    case_id = create_case(client)
    upload(client, case_id)
    ingest(client, case_id)
    r = client.post(f"{API}/cases/{case_id}/verify", json={"claim": "Нещо"})
    assert r.status_code == 503
    assert r.json()["error"]["code"] == "llm_unavailable"


def test_unknown_case_returns_case_not_found(client):
    r = client.post(f"{API}/cases/nope/verify", json={"claim": "abc"})
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "case_not_found"


def test_verify_claim_length_validated(client):
    case_id = create_case(client)
    r = client.post(f"{API}/cases/{case_id}/verify", json={"claim": "ab"})
    assert r.status_code == 422


def test_old_flat_routes_are_gone(client):
    assert client.get("/api/health").status_code == 404
    assert client.post("/api/cases", json={"title": "x"}).status_code == 404
