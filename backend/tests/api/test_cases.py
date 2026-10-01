"""Case CRUD and lifecycle status transitions."""

from __future__ import annotations

from tests.api.helpers import API, create_case, ingest, upload


def test_create_case_defaults(client):
    r = client.post(f"{API}/cases", json={"title": "Дело 1", "description": "Бележка"})
    assert r.status_code == 201
    case = r.json()
    assert case["status"] == "empty"
    assert case["document_count"] == 0
    assert case["chunk_count"] == 0
    assert case["ingested_at"] is None
    assert case["created_at"] == case["updated_at"]


def test_create_case_validation(client):
    assert client.post(f"{API}/cases", json={"title": ""}).status_code == 422
    r = client.post(f"{API}/cases", json={"title": "x" * 201})
    assert r.json()["error"]["code"] == "validation_error"
    r = client.post(f"{API}/cases", json={"title": "ok", "description": "d" * 2001})
    assert r.status_code == 422


def test_list_cases_newest_first_with_paging(client):
    ids = [create_case(client, f"Дело {i}") for i in range(3)]
    listed = [c["id"] for c in client.get(f"{API}/cases").json()]
    assert listed == list(reversed(ids))
    page = client.get(f"{API}/cases", params={"skip": 1, "limit": 1}).json()
    assert [c["id"] for c in page] == [ids[1]]
    assert client.get(f"{API}/cases", params={"limit": 0}).status_code == 422


def test_patch_case(client):
    case_id = create_case(client, "Старо", description="описание")
    r = client.patch(f"{API}/cases/{case_id}", json={"title": "Ново"})
    assert r.status_code == 200
    body = r.json()
    assert body["title"] == "Ново"
    assert body["description"] == "описание"
    assert body["updated_at"] >= body["created_at"]

    r = client.patch(f"{API}/cases/{case_id}", json={"description": None})
    assert r.json()["description"] is None
    assert r.json()["title"] == "Ново"

    r = client.patch(f"{API}/cases/missing", json={"title": "x"})
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "case_not_found"


def test_delete_case_removes_uploads_and_collection(client, isolated_env):
    case_id = create_case(client)
    upload(client, case_id)
    ingest(client, case_id)
    assert (isolated_env / "uploads" / case_id).exists()

    r = client.delete(f"{API}/cases/{case_id}")
    assert r.status_code == 204
    assert r.content == b""
    assert client.get(f"{API}/cases/{case_id}").status_code == 404
    assert not (isolated_env / "uploads" / case_id).exists()

    from app.services.vector_store import get_vectorstore

    assert get_vectorstore().count(case_id) == 0
    assert client.delete(f"{API}/cases/{case_id}").status_code == 404


def test_lifecycle_transitions(client):
    case_id = create_case(client)

    def status() -> str:
        return client.get(f"{API}/cases/{case_id}").json()["status"]

    assert status() == "empty"
    doc1 = upload(client, case_id).json()["id"]
    assert status() == "uploaded"

    ingest(client, case_id)
    case = client.get(f"{API}/cases/{case_id}").json()
    assert case["status"] == "ingested"
    assert case["chunk_count"] >= 1
    assert case["ingested_at"] is not None

    doc2 = upload(client, case_id, name="vtori.txt").json()["id"]
    assert status() == "stale"
    ingest(client, case_id)
    assert status() == "ingested"

    assert client.delete(f"{API}/cases/{case_id}/documents/{doc2}").status_code == 204
    assert status() == "stale"
    assert client.delete(f"{API}/cases/{case_id}/documents/{doc1}").status_code == 204
    case = client.get(f"{API}/cases/{case_id}").json()
    assert case["status"] == "empty"
    assert case["chunk_count"] == 0
    assert case["ingested_at"] is None


def test_legacy_index_is_normalised(isolated_env):
    import json

    from app.services.storage import CaseStore

    isolated_env.mkdir(parents=True, exist_ok=True)
    legacy = {
        "c1": {
            "id": "c1",
            "title": "Legacy",
            "description": None,
            "created_at": "2025-01-01T00:00:00+00:00",
            "documents": [{"id": "d1", "case_id": "c1", "filename": "a.txt"}],
            "ingested": True,
        }
    }
    (isolated_env / "cases_index.json").write_text(json.dumps(legacy), "utf-8")
    case = CaseStore().require_case("c1")
    assert case["status"] == "ingested"
    assert case["updated_at"] == case["created_at"]
    assert "ingested" not in case
