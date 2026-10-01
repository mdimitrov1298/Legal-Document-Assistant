# Legal Document Assistant (Diploma Prototype)

Local retrieval-augmented assistant for **Bulgarian case documents**. A user
creates a case, uploads PDF or TXT files, ingests them into a local vector
store, gets a summary with citations and checks a claim against the documents.
The verdict is `supported`, `denied` or `inconclusive`, always backed by quotes
that are flagged as verbatim or not.

**upload -> ingest (extract, chunk, embed, Chroma) -> summarize with citations -> verify a claim with quotes**

Everything runs on the local machine: generation through a local Ollama,
embeddings on CPU, persistent Chroma on disk. No cloud LLM API ever receives
case content. The target machine has about 16 GB of RAM.

## Stack

| Layer | Choice |
|-------|--------|
| API | FastAPI (Python 3.12), versioned under `/api/v1`, uniform error envelope |
| UI | React 19 + Vite + TypeScript, plain CSS, Bulgarian UI copy |
| LLM runtime | Ollama only: default `qwen2.5:7b`; A/B `bggpt-7b` (imported GGUF); control `llama3.1:8b` |
| Embeddings | `sentence-transformers/all-MiniLM-L6-v2` on CPU (default); optional Ollama `nomic-embed-text`; `hash_stub` for CI/offline |
| Vector store | Chroma `PersistentClient`, one collection per case |
| Formats | PDF and TXT, Bulgarian only |
| Tooling | ruff, pytest, pre-commit, ESLint, Prettier, Docker Compose, GitHub Actions |

## Scope and non-goals

In scope: factual summaries of the uploaded documents and claim checks that
cite the retrieved text.

Out of scope, by design:

- legal advice, interpretation or conclusions;
- legal classification of cases;
- building timelines or chronologies as analysis;
- English or other non-Bulgarian case material;
- cloud LLM APIs for case content, authentication or multi-user deployment.

## Quick start (local)

Requirements: Python 3.12+, Node 20.19+ (or 22.12+), [Ollama](https://ollama.com).

```bash
# 1. Ollama (separate terminal)
ollama serve
ollama pull qwen2.5:7b

# 2. Backend
cp .env.example .env
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install --index-url https://download.pytorch.org/whl/cpu torch   # CPU-only torch
pip install -r requirements-dev.txt
cd ..
PYTHONPATH=backend backend/.venv/bin/python -m uvicorn app.main:app \
  --app-dir backend --host 127.0.0.1 --port 8000 --reload --no-access-log

# 3. Frontend (separate terminal)
cd frontend
npm install
npm run dev
```

Run the API from the repository root so `./data` and `.env` resolve there.
Open http://127.0.0.1:5173 (the Vite dev server proxies `/api` to port 8000)
and the interactive API docs at http://127.0.0.1:8000/docs.

```bash
curl -s http://127.0.0.1:8000/health            # liveness: {"status":"ok"}
curl -s http://127.0.0.1:8000/api/v1/health     # Ollama, model, embeddings, store
```

Demo flow: create a case, upload the files from [`samples/`](./samples/),
ingest, summarize, then verify for example *Възнаграждението е 4500 лв.*

If Ollama is down, summarize and verify still answer with `stubbed: true`
and citations taken directly from the retrieved chunks, and
`/api/v1/health` reports `status: "degraded"`. Ingest does not need Ollama
with the default MiniLM embeddings.

### Using BgGPT

BgGPT has no official Ollama tag. Import the GGUF and point the API at it:

```bash
# Modelfile containing: FROM ./BgGPT-7B-Instruct-v0.2.Q4_K_M.gguf
ollama create bggpt-7b -f Modelfile
OLLAMA_MODEL=bggpt-7b   # in .env
```

When the model name contains `bggpt`, the API renders the Mistral
`[INST] ... [/INST]` template itself and sends the prompt in raw mode, so the
Modelfile does not need a `TEMPLATE`. System prompts stay identical across
models.

## Quick start (Docker Compose)

```bash
docker compose up --build
docker compose exec ollama ollama pull qwen2.5:7b
```

| Service | URL | Notes |
|---------|-----|-------|
| frontend | http://localhost:8080 | nginx serving the build, proxies `/api` to the backend |
| backend | http://localhost:8000/docs | CPU-only image, non-root, MiniLM baked in, data in the `backend-data` volume |
| ollama | http://localhost:11434 | models in the `ollama` volume |

Override `OLLAMA_MODEL`, `OLLAMA_NUM_CTX`, `EMBEDDING_BACKEND` or
`MAX_UPLOAD_MB` through the shell environment or a root `.env` read by Compose.

## Configuration

Settings come from environment variables or `.env` (see
[`.env.example`](./.env.example)).

| Variable | Default | Meaning |
|----------|---------|---------|
| `APP_ENV` | `local` | `local`, `test` or `production` |
| `LOG_LEVEL` | `INFO` | Root log level |
| `LOG_FORMAT` | `text` | `text` or `json` (one JSON object per line, includes `request_id`) |
| `OLLAMA_BASE_URL` | `http://127.0.0.1:11434` | Ollama HTTP API |
| `OLLAMA_MODEL` | `qwen2.5:7b` | Active generation model (must be pulled) |
| `OLLAMA_NUM_CTX` | `4096` | Context window passed as `options.num_ctx` |
| `OLLAMA_TEMPERATURE` | `0.0` | Sampling temperature passed as `options.temperature` |
| `OLLAMA_STUB_ON_UNAVAILABLE` | `true` | Stub answers when Ollama fails; `false` returns 503 `llm_unavailable` |
| `OLLAMA_HEALTH_TIMEOUT` | `3.0` | Seconds for `/api/tags` probes |
| `OLLAMA_GENERATE_TIMEOUT` | `120.0` | Seconds for `/api/generate` (7B on CPU can be slow) |
| `EMBEDDING_BACKEND` | `sentence-transformers` | `sentence-transformers`, `ollama` or `hash_stub` |
| `EMBEDDING_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` | Model id for the backend |
| `EMBEDDING_DEVICE` | `cpu` | Device for sentence-transformers |
| `CHUNK_SIZE` / `CHUNK_OVERLAP` | `800` / `120` | Characters per chunk and overlap |
| `SUMMARIZE_TOP_K` / `VERIFY_TOP_K` | `8` / `5` | Default retrieved chunks when a request omits `top_k` |
| `MAX_UPLOAD_MB` | `20` | Upload size limit (413 `payload_too_large` above it) |
| `DATA_DIR` | `./data` | Case index (`cases_index.json`) |
| `CHROMA_PATH` | `./data/chroma` | Persistent vector store |
| `UPLOAD_DIR` | `./data/uploads` | Uploaded files |
| `API_HOST` / `API_PORT` | `0.0.0.0` / `8000` | Used by `backend/run.py` |
| `CORS_ORIGINS` | Vite localhost URLs | Comma-separated allowed origins |

If the configured embedding backend cannot load, ingest falls back to
`hash_stub` and `/api/v1/health` shows both `backend` and
`backend_configured`.

## API summary

Full reference: [docs/api-endpoints.md](./docs/api-endpoints.md). Interactive
schema: `/docs` and `/openapi.json` (operation IDs equal the route function
names).

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/` | Service name, version, docs link |
| GET | `/health` | Liveness only |
| GET | `/api/v1/health` | Ollama reachability and model, embeddings, vector store, chunking; `ok` or `degraded` |
| GET | `/api/v1/models` | Active model and installed Ollama models |
| POST | `/api/v1/cases` | Create a case |
| GET | `/api/v1/cases` | List cases, newest first (`skip`, `limit`) |
| GET / PATCH / DELETE | `/api/v1/cases/{case_id}` | Read, update or delete a case (delete removes uploads and the collection) |
| GET / POST | `/api/v1/cases/{case_id}/documents` | List or upload documents (PDF/TXT, sha256 recorded) |
| DELETE | `/api/v1/cases/{case_id}/documents/{document_id}` | Delete a document and its chunks |
| POST | `/api/v1/cases/{case_id}/ingest` | Extract, chunk, embed; rebuilds the case collection |
| GET | `/api/v1/cases/{case_id}/index` | Index statistics |
| POST | `/api/v1/cases/{case_id}/summarize` | Summary with citations |
| POST | `/api/v1/cases/{case_id}/verify` | Claim verdict with supporting, denying and retrieved quotes |

Case status follows `empty -> uploaded -> ingested -> stale -> ingested`;
summarize and verify need `ingested` or `stale` (otherwise 409
`case_not_ingested`). Every citation carries `chunk_index` and `verbatim`
(true when the quote occurs in the stored chunk after whitespace
normalisation).

Every non-2xx response has the same shape and every response carries
`X-Request-ID`:

```json
{
  "error": { "code": "case_not_found", "message": "Case not found", "details": null },
  "request_id": "5f0c6f7e-8c1b-4d0e-9f59-0c7d1b1f2a3b"
}
```

Codes: `validation_error` 422, `case_not_found` 404, `document_not_found` 404,
`unsupported_media_type` 415, `payload_too_large` 413, `empty_file` 400,
`no_documents` 409, `case_not_ingested` 409, `ingest_failed` 500,
`llm_unavailable` 503, `internal_error` 500.

## Documentation

| Document | Content |
|----------|---------|
| [docs/PRD.md](./docs/PRD.md) | Product requirements |
| [docs/architecture-diagrams.md](./docs/architecture-diagrams.md) | Architecture and sequence diagrams |
| [docs/api-endpoints.md](./docs/api-endpoints.md) | Complete endpoint reference |
| [docs/architecture.md](./docs/architecture.md) | Architecture chapter of the thesis (Bulgarian) |
| [ARCHITECTURE.md](./ARCHITECTURE.md) | Short engineering overview and code layout |
| [eval/eval-v0.1/README.md](./eval/eval-v0.1/README.md) | Evaluation package (draft) |

## Evaluation harness

[`eval/eval-v0.1/`](./eval/eval-v0.1/) is a **draft** Bulgarian evaluation
package: synthetic passages P1, P2 and P4, a pending slot P3 for an
EUR-Lex-Sum Bulgarian text, and 18 seed claims with gold labels and evidence
spans. It is not frozen yet, and no results are published in this repository.

```bash
cd backend
source .venv/bin/activate
python -m app.eval.run --package ../eval/eval-v0.1 --model qwen2.5:7b \
  --num-ctx 4096 --top-k 5 --out ../eval/runs
python -m app.eval.score ../eval/runs/<run>.jsonl          # markdown table
python -m app.eval.score ../eval/runs/<run>.jsonl --json   # machine-readable
```

The runner uses an isolated temporary data directory, so the regular case
store is untouched. Each run file records the git commit, model tag, Ollama
version, `num_ctx`, temperature, top-k, chunking, embedding backend, prompt
version and package hash. The scorer reports label accuracy, macro-F1, NEI
precision and recall, verbatim citation rate and median latency, and marks
runs with stubbed outputs, errors or `hash_stub` embeddings as not valid for
model comparison. Keep the retrieval settings fixed and change only
`--model` between A/B runs.

## Tests and lint

```bash
cd backend
source .venv/bin/activate
pytest -q                 # hash_stub embeddings and mocked Ollama, no network
ruff check && ruff format --check
pre-commit install        # optional: run ruff and basic hooks on commit
```

A live Ollama test skips automatically when the daemon is not running. CI
(`.github/workflows/ci.yml`) runs ruff and pytest for the backend and lint,
typecheck and build for the frontend.

## Notes for 16 GB RAM

1. Run one 7B or 8B model at a time; Q4 weights take about 4.4 to 4.9 GB.
2. Keep `OLLAMA_NUM_CTX` moderate (4096 or 8192); the KV cache grows with it.
3. Keep `EMBEDDING_DEVICE=cpu` and MiniLM (about 80 MB) next to the LLM.
4. Close other heavy applications if Ollama starts swapping.

## Academic use

This is a diploma research prototype, not a legal advice product. Outputs
must be checked by a person against the cited quotes. Sample files in
`samples/` and passages in `eval/` are original synthetic Bulgarian texts;
they describe fictional people and companies.
