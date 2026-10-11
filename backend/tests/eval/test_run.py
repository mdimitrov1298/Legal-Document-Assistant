"""Runner end-to-end with a mocked Ollama and hash_stub embeddings."""

from __future__ import annotations

import json
import os
from pathlib import Path

import httpx
import pytest

from app.core.config import get_settings
from app.eval.run import RunConfig, build_parser, run_evaluation
from app.eval.score import load_run, score_records
from app.services.llm import OllamaClient

PACKAGE = Path(__file__).resolve().parents[3] / "eval" / "eval-v0.1"


def _mock_ollama(request: httpx.Request) -> httpx.Response:
    if request.url.path == "/api/tags":
        return httpx.Response(200, json={"models": [{"name": "qwen2.5:7b"}]})
    if request.url.path == "/api/version":
        return httpx.Response(200, json={"version": "0.0-test"})
    body = json.loads(request.content)
    if "ТВЪРДЕНИЕ" in body["prompt"]:
        first_chunk = body["prompt"].split("[0] ", 1)[1].split("\n", 1)[1]
        answer = {
            "verdict": "supported",
            "rationale": "Цитат [0].",
            "supporting_quotes": [{"index": 0, "quote": first_chunk[:40]}],
            "denying_quotes": [],
        }
    else:
        answer = {"summary": "Кратко резюме.", "citation_indices": [0]}
    return httpx.Response(200, json={"response": json.dumps(answer)})


def _down(request: httpx.Request) -> httpx.Response:
    raise httpx.ConnectError("down", request=request)


def _client(handler) -> OllamaClient:
    return OllamaClient(get_settings(), transport=httpx.MockTransport(handler))


async def test_run_writes_metadata_and_records(tmp_path: Path):
    out = tmp_path / "runs"
    before = dict(os.environ)
    path = await run_evaluation(
        RunConfig(package=PACKAGE, out_dir=out), llm=_client(_mock_ollama)
    )
    assert dict(os.environ) == before
    assert path.parent == out
    assert path.name.endswith("_qwen2.5-7b_ctx4096_k5.jsonl")

    header, records, footer = load_run(path)
    assert header["model"] == "qwen2.5:7b"
    assert header["ollama"] == {
        "base_url": "http://ollama.test",
        "reachable": True,
        "version": "0.0-test",
    }
    assert header["num_ctx"] == 4096
    assert header["temperature"] == 0.0
    assert header["top_k"] == 5
    assert header["chunk_size"] == 800
    assert header["embedding_backend"] == "hash_stub"
    assert header["package"]["status"] == "frozen"
    assert header["package"]["manifest_sha256"].startswith("sha256:")
    assert header["prompt_version"]
    assert header["prompt_versions"] == {"bg": "bg-v1", "en": "en-v1"}
    assert "commit" in header["git"]

    kinds = [r["type"] for r in records]
    assert kinds.count("ingest") == 4
    assert kinds.count("summary") == 4
    assert kinds.count("verify") == 25
    verify = [r for r in records if r["type"] == "verify"]
    assert {r["predicted_label"] for r in verify} == {"SUPPORTED"}
    assert all(r["stubbed"] is False for r in verify)
    assert all(r["supporting_quotes"][0]["verbatim"] for r in verify)
    p4_ingest = next(
        r for r in records if r["type"] == "ingest" and r["passage_id"] == "P4"
    )
    assert p4_ingest["documents"] == ["P4", "P2"]
    assert footer["stubbed_outputs"] == 0
    assert footer["errors"] == 0
    assert footer["harness_peak_rss_bytes"] > 0
    assert all("retrieval_ms" in r and "generation_ms" in r for r in verify)
    assert all(r.get("answer_language") == "bg" for r in verify)
    assert all(r.get("prompt_version") == "bg-v1" for r in verify)
    summaries = [r for r in records if r["type"] == "summary"]
    assert all(r.get("answer_language") == "bg" for r in summaries)
    assert all(r.get("prompt_version") == "bg-v1" for r in summaries)

    result = score_records(header, records, footer)
    assert result["claims_scored"] == 25
    assert result["label_accuracy"] == pytest.approx(9 / 25)
    assert result["verbatim_citation_rate"] == 1.0
    assert result["valid_for_comparison"] is False
    assert any("hash_stub" in r for r in result["invalid_reasons"])


async def test_stubbed_run_is_flagged(tmp_path: Path):
    path = await run_evaluation(
        RunConfig(package=PACKAGE, out_dir=tmp_path, top_k=3, num_ctx=8192),
        llm=_client(_down),
    )
    header, records, footer = load_run(path)
    assert header["ollama"]["reachable"] is False
    assert header["ollama"]["version"] is None
    assert footer["stubbed_outputs"] == 29
    result = score_records(header, records, footer)
    assert result["valid_for_comparison"] is False
    assert any("stubbed" in r for r in result["invalid_reasons"])
    assert result["per_scenario"]["S5"]["accuracy"] == 1.0


async def test_explicit_work_dir_is_kept(tmp_path: Path):
    work = tmp_path / "work"
    await run_evaluation(
        RunConfig(package=PACKAGE, out_dir=tmp_path / "o", work_dir=work),
        llm=_client(_down),
    )
    assert (work / "data" / "cases_index.json").exists()


PACKAGE_EN = Path(__file__).resolve().parents[3] / "eval" / "eval-en-v0.1"


def _mock_ollama_en(request: httpx.Request) -> httpx.Response:
    if request.url.path == "/api/tags":
        return httpx.Response(200, json={"models": [{"name": "qwen2.5:7b"}]})
    if request.url.path == "/api/version":
        return httpx.Response(200, json={"version": "0.0-test"})
    body = json.loads(request.content)
    if "CLAIM" in body["prompt"]:
        first_chunk = body["prompt"].split("[0] ", 1)[1].split("\n", 1)[1]
        answer = {
            "verdict": "supported",
            "rationale": "Quote [0].",
            "supporting_quotes": [{"index": 0, "quote": first_chunk[:40]}],
            "denying_quotes": [],
        }
    else:
        answer = {"summary": "Short summary.", "citation_indices": [0]}
    return httpx.Response(200, json={"response": json.dumps(answer)})


async def test_en_run_records_en_prompt_version(tmp_path: Path):
    """EN eval package records en-v1 prompt version in header and records."""
    if not PACKAGE_EN.exists():
        pytest.skip("eval-en-v0.1 package not present")
    path = await run_evaluation(
        RunConfig(package=PACKAGE_EN, out_dir=tmp_path / "runs"),
        llm=_client(_mock_ollama_en),
    )
    header, records, _ = load_run(path)
    assert header["prompt_versions"]["en"] == "en-v1"
    verify = [r for r in records if r["type"] == "verify"]
    assert all(r.get("answer_language") == "en" for r in verify)
    assert all(r.get("prompt_version") == "en-v1" for r in verify)
    summaries = [r for r in records if r["type"] == "summary"]
    assert all(r.get("answer_language") == "en" for r in summaries)
    assert all(r.get("prompt_version") == "en-v1" for r in summaries)


def test_cli_arguments_map_to_config():
    args = build_parser().parse_args(
        [
            "--package",
            "../eval/eval-v0.1",
            "--model",
            "bggpt-7b",
            "--num-ctx",
            "4096",
            "--top-k",
            "5",
            "--out",
            "../eval/runs",
            "--no-stub",
        ]
    )
    assert args.model == "bggpt-7b"
    assert args.num_ctx == 4096
    assert args.top_k == 5
    assert args.out_dir == Path("../eval/runs")
    assert args.no_stub is True
