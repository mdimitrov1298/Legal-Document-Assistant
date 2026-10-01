# Architecture (engineering overview)

Thesis chapter in Bulgarian: [`docs/architecture.md`](./docs/architecture.md).
Diagrams: [`docs/architecture-diagrams.md`](./docs/architecture-diagrams.md).
Endpoint reference: [`docs/api-endpoints.md`](./docs/api-endpoints.md).

## Goal

Local research prototype for Bulgarian case documents:
**upload -> ingest -> summarize with citations -> verify a claim with quotes**.
Ollama is the only LLM runtime, no cloud LLM API sees case content, and the
whole stack fits a machine with about 16 GB of RAM. Legal interpretation,
classification, timelines and legal conclusions are explicit non-goals.

## Repository layout

```
legal/
  README.md, ARCHITECTURE.md, .env.example
  ruff.toml, .pre-commit-config.yaml, compose.yml, .dockerignore
  .github/workflows/ci.yml        backend (ruff, pytest) and frontend (lint, typecheck, build)
  data/                           runtime data, gitignored (case index, uploads, chroma)
  samples/                        synthetic Bulgarian demo documents
  docs/                           PRD, diagrams, endpoint reference, thesis chapter
  eval/
    eval-v0.1/                    draft evaluation package (manifest, passages, claims)
    runs/                         evaluation outputs, gitignored
  backend/
    Dockerfile, requirements.txt, requirements-dev.txt, pytest.ini, run.py
    app/
      main.py                     create_app(): CORS, middleware, handlers, routers
      core/
        config.py                 pydantic-settings Settings
        logging.py                text or JSON logs with request_id
        errors.py                 AppError hierarchy and envelope handlers
        middleware.py             X-Request-ID and access log with duration
      routes/                     api_router under /api/v1: system, cases, documents, rag
      schemas/                    common (error envelope), system, cases, documents, rag
      services/
        storage.py                JSON case index (atomic writes, lock) and uploads
        extraction.py             upload validation, PDF/TXT text extraction
        chunking.py               overlapping character chunks
        embeddings.py             MiniLM, Ollama or hash_stub embeddings
        vector_store.py           Chroma collection per case
        llm.py                    Ollama client with stub fallback
        prompts.py                Bulgarian prompts and BgGPT [INST] template
        citations.py              verbatim quote check
        pipeline.py               ingest, summarize, verify
      eval/
        manifest.py               package loader and integrity checks
        run.py                    python -m app.eval.run
        score.py                  python -m app.eval.score
    tests/
      conftest.py                 temp data dirs, hash_stub embeddings, mocked Ollama
      api/, services/, eval/
  frontend/                       React + Vite + TypeScript (see frontend/README.md)
```

## Request handling

1. `RequestContextMiddleware` (pure ASGI) reads or generates `X-Request-ID`,
   stores it in a context variable for logging, adds it to the response and
   writes one access log line with method, path, status and `duration_ms`.
2. Routes validate input with Pydantic schemas and call services.
3. Services raise `AppError` subclasses (`case_not_found`, `no_documents`,
   `case_not_ingested`, `payload_too_large` and so on). Exception handlers turn
   them, request validation errors, HTTP errors and unexpected exceptions into
   `{"error": {"code", "message", "details"}, "request_id"}`.

## Case lifecycle

| Status | Meaning | Next |
|--------|---------|------|
| `empty` | No documents | upload -> `uploaded` |
| `uploaded` | Documents, never ingested | ingest -> `ingested` |
| `ingested` | Index matches the documents | upload or delete document -> `stale` |
| `stale` | Documents changed since the last ingest | ingest -> `ingested`; delete last document -> `empty` |

Summarize and verify accept `ingested` and `stale` cases. Deleting a document
also deletes its chunks from Chroma; deleting a case removes its uploads and
collection.

## Data flow

```
Browser (Vite 5173 or nginx 8080)
  |  /api/v1/...
  v
FastAPI
  upload   -> validate type/size, sha256 -> data/uploads/{case_id}/ + cases_index.json
  ingest   -> extract -> chunk (CHUNK_SIZE/CHUNK_OVERLAP) -> embed -> Chroma case_<id>
  summarize-> retrieve top-k by case title -> Ollama JSON {summary, citation_indices}
  verify   -> retrieve top-k by claim -> Ollama JSON {verdict, rationale, quotes}
              -> citations with chunk_index and verbatim flag
  v
Ollama (localhost or compose service)      Chroma (CHROMA_PATH on disk)
```

## LLM, prompts and stubs

- `llm.OllamaClient` calls `POST /api/generate` with `options.num_ctx` and
  `options.temperature` from settings. `/api/tags` drives health and
  `/api/models`; `/api/version` is recorded in evaluation runs.
- `prompts.py` holds the Bulgarian system prompts shared by all models and a
  `PROMPT_VERSION`. For models whose name contains `bggpt` the Mistral
  `[INST] ... [/INST]` template is rendered in the API and sent with
  `raw: true`.
- When Ollama fails and `OLLAMA_STUB_ON_UNAVAILABLE=true`, a deterministic
  stub answer is returned with `stubbed: true`; otherwise the API returns 503
  `llm_unavailable`.

## Citations

Summaries cite retrieved chunks by index; verify answers may carry
`{index, quote}` pairs. `citations.py` marks a quote as `verbatim` when, after
Unicode NFC normalisation, whitespace collapsing and removal of enclosing
quotation marks, it is an exact substring of the stored chunk text.
Non-verbatim quotes are kept and flagged so the UI and the scorer can show
them.

## Evaluation

`app.eval.run` loads a package (hashes and gold spans are validated), runs each
passage in a temporary case inside an isolated data directory, and writes a
JSONL run with metadata (commit, model tag, Ollama version, num_ctx,
temperature, top-k, chunking, embedding backend, prompt version, package hash).
`app.eval.score` computes label accuracy, macro-F1, NEI precision and recall,
verbatim citation rate and median latency, and flags runs with stubbed outputs,
errors or `hash_stub` embeddings as not valid for model comparison.

## Memory notes (16 GB)

- One quantised 7B or 8B model in Ollama at a time.
- MiniLM embeddings on CPU (about 80 MB) leave headroom for the LLM.
- `OLLAMA_NUM_CTX` 4096 by default; 8192 is a separate evaluation series.
