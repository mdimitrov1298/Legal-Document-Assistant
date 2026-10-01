# Legal Document Assistant API - Complete Endpoints List

Base URL: `http://127.0.0.1:8000`. Versioned endpoints live under `/api/v1`. In development the Vite dev server on port 5173 proxies `/api` to port 8000, so the browser calls the same paths on its own origin. With the optional docker compose setup the web UI is served by nginx on port 8080, which proxies `/api` to `backend:8000`. Current API version: `0.2.0`.

Conventions:

- All request and response bodies are JSON, except document upload (`multipart/form-data`).
- Every response carries an `X-Request-ID` header. If the client sends one it is echoed, otherwise the API generates a UUID.
- Every non-2xx response uses the same error envelope with a snake_case `code` (see [Error Envelope](#error-envelope)).
- Identifiers (`case_id`, `document_id`) are UUID strings. Timestamps are ISO 8601 datetimes.
- Schemas referenced below are listed in [Common Schemas](#common-schemas).
- There is no authentication: the API binds to the local machine and serves a single user.

---

## System Endpoints

### GET /api/v1/health

- **Description**: Readiness and configuration report: API version, Ollama reachability, active model and whether it is pulled, embedding backend, vector store path and chunking parameters
- **Response**: `HealthResponse { status: "ok" | "degraded", version, ollama: { reachable, base_url, model, model_present, models_installed }, embeddings: { backend, backend_configured, model, device }, vector_store: { path }, chunking: { size, overlap } }` (200 OK)
- **Errors**: `internal_error` (500)
- **Notes**:
    - `status` is `degraded` when Ollama is unreachable or the configured model is not pulled; the endpoint still returns 200
    - `version` is the API version (currently `0.2.0`)
    - `ollama.model_present` is `null` when Ollama is unreachable
    - `embeddings.backend` is the backend actually in use; `backend_configured` is the value from `EMBEDDING_BACKEND` (they differ after a fallback to `hash_stub`)
- **Auth Required**: No (local single-user prototype)

### GET /api/v1/models

- **Description**: Active generation model and the models installed in the local Ollama
- **Response**: `{ "active": "string", "reachable": bool, "installed": ["string"] }` (200 OK)
- **Errors**: `internal_error` (500)
- **Notes**: `active` is the value of `OLLAMA_MODEL` (for example `qwen2.5:7b`, `bggpt-7b` or `llama3.1:8b`). `installed` is empty when Ollama is unreachable
- **Auth Required**: No (local single-user prototype)

---

## Cases Endpoints

### POST /api/v1/cases

- **Description**: Create a new case
- **Request Body**: `CaseCreate { "title": "string" (1..200), "description": "string" (optional, max 2000) }`
- **Response**: `CaseResponse` (201 Created)
- **Errors**: `validation_error` (422)
- **Notes**: A new case starts with `status = "empty"`, `document_count = 0`, `chunk_count = 0`, `ingested_at = null`
- **Auth Required**: No (local single-user prototype)

### GET /api/v1/cases

- **Description**: List cases, newest first
- **Query Parameters**: `skip` (int, default: 0), `limit` (int, default: 100)
- **Response**: `List[CaseResponse]` (200 OK)
- **Errors**: `validation_error` (422)
- **Auth Required**: No (local single-user prototype)

### GET /api/v1/cases/{case_id}

- **Description**: Get a case by ID
- **Path Parameters**: `case_id` (UUID)
- **Response**: `CaseResponse` (200 OK)
- **Errors**: `case_not_found` (404)
- **Auth Required**: No (local single-user prototype)

### PATCH /api/v1/cases/{case_id}

- **Description**: Update case title and/or description
- **Path Parameters**: `case_id` (UUID)
- **Request Body**: `CaseUpdate { "title": "string" (optional, 1..200), "description": "string" (optional, max 2000) }`
- **Response**: `CaseResponse` (200 OK)
- **Errors**: `case_not_found` (404), `validation_error` (422)
- **Notes**: Only the provided fields change; `updated_at` is refreshed. The case `status` is not affected
- **Auth Required**: No (local single-user prototype)

### DELETE /api/v1/cases/{case_id}

- **Description**: Delete a case with all its data
- **Path Parameters**: `case_id` (UUID)
- **Response**: 204 No Content
- **Errors**: `case_not_found` (404)
- **Notes**: Removes the case record, its uploaded files and its Chroma collection
- **Auth Required**: No (local single-user prototype)

---

## Documents Endpoints

### GET /api/v1/cases/{case_id}/documents

- **Description**: List documents uploaded to a case
- **Path Parameters**: `case_id` (UUID)
- **Response**: `List[DocumentResponse]` (200 OK)
- **Errors**: `case_not_found` (404)
- **Auth Required**: No (local single-user prototype)

### POST /api/v1/cases/{case_id}/documents

- **Description**: Upload one Bulgarian PDF or TXT document to a case
- **Path Parameters**: `case_id` (UUID)
- **Request Body**: `multipart/form-data` with field `file`
- **Response**: `DocumentResponse` (201 Created)
- **Errors**: `case_not_found` (404), `unsupported_media_type` (415), `payload_too_large` (413), `empty_file` (400), `validation_error` (422)
- **Notes**:
    - Validation order: size (above `MAX_UPLOAD_MB`, default 20, gives 413), suffix (only `.pdf` and `.txt`, otherwise 415), declared content type must match the suffix (`application/pdf` or `application/x-pdf` for PDF, `text/plain` for TXT; `application/octet-stream` or none is accepted), empty file (400), and for PDFs the content must start with `%PDF` (otherwise 415)
    - The stored `content_type` is canonical: `application/pdf` or `text/plain`
    - The API stores the file under the case upload directory and records its `sha256`
    - Case status changes: `empty` to `uploaded`, `ingested` to `stale`
- **Auth Required**: No (local single-user prototype)

### DELETE /api/v1/cases/{case_id}/documents/{document_id}

- **Description**: Delete one document from a case
- **Path Parameters**: `case_id` (UUID), `document_id` (UUID)
- **Response**: 204 No Content
- **Errors**: `case_not_found` (404), `document_not_found` (404)
- **Notes**:
    - Removes the uploaded file, the document record and the document's chunks from the case's Chroma collection (`chunk_count` is updated)
    - Case status changes: `ingested` or `stale` to `stale`; deleting the last document returns the case to `empty` and clears the collection
- **Auth Required**: No (local single-user prototype)

---

## Ingest & Index Endpoints

### POST /api/v1/cases/{case_id}/ingest

- **Description**: Extract text from all case documents, split into chunks, embed and write them to the case's Chroma collection
- **Path Parameters**: `case_id` (UUID)
- **Request Body**: None
- **Response**: `IngestResponse { case_id, documents_processed, chunks_indexed, embedding_backend, embedding_model, chunk_size, chunk_overlap, vector_store_path, persisted, duration_ms }` (200 OK)
- **Errors**: `case_not_found` (404), `no_documents` (409), `ingest_failed` (500)
- **Notes**:
    - Re-ingest rebuilds the collection from scratch (no duplicate chunks)
    - Text is extracted from all documents before the collection is touched: a document whose extraction raises an error, or a case where no document yields any text, returns 500 `ingest_failed` and the existing index is left untouched
    - Documents whose file is missing on disk are skipped with a warning
    - Does not call Ollama when the embedding backend is `sentence-transformers` or `hash_stub`
    - If the configured embedding backend cannot be initialised, ingest falls back to `hash_stub` and reports it in `embedding_backend`
    - `persisted` is true when the collection count matches `chunks_indexed`
    - On success the case status becomes `ingested`
- **Auth Required**: No (local single-user prototype)

### GET /api/v1/cases/{case_id}/index

- **Description**: Statistics of the case's vector index
- **Path Parameters**: `case_id` (UUID)
- **Response**: `IndexStatsResponse { case_id, collection, chunk_count, embedding_backend, embedding_model, ingested_at }` (200 OK)
- **Errors**: `case_not_found` (404)
- **Notes**: `chunk_count` is read live from Chroma. `embedding_backend`, `embedding_model` and `ingested_at` are `null` for a case that has never been ingested
- **Auth Required**: No (local single-user prototype)

---

## Summarize & Verify Endpoints

### POST /api/v1/cases/{case_id}/summarize

- **Description**: Factual Bulgarian summary of the case, built only from retrieved chunks, with citations
- **Path Parameters**: `case_id` (UUID)
- **Request Body**: `SummarizeRequest { "top_k": int | null (1..20) }` (the body or `top_k` may be omitted; then `SUMMARIZE_TOP_K`, default 8, is used)
- **Response**: `SummarizeResponse { case_id, summary, citations: Citation[], model, stubbed, chunks_used, duration_ms }` (200 OK)
- **Errors**: `case_not_found` (404), `case_not_ingested` (409), `validation_error` (422), `llm_unavailable` (503), `internal_error` (500)
- **Notes**:
    - Allowed only when the case status is `ingested` or `stale`
    - Each citation carries `verbatim`; quotes the model did not copy exactly from the chunk are kept with `verbatim = false`
    - `stubbed = true` means Ollama was not used and the summary is assembled from raw chunk excerpts
    - `llm_unavailable` is returned only when `OLLAMA_STUB_ON_UNAVAILABLE=false`
    - The output is not legal advice
- **Auth Required**: No (local single-user prototype)

### POST /api/v1/cases/{case_id}/verify

- **Description**: Check a factual claim against the case documents and return a verdict with quotes
- **Path Parameters**: `case_id` (UUID)
- **Request Body**: `VerifyRequest { "claim": "string" (3..1000 chars), "top_k": int | null (1..20) }` (when `top_k` is omitted or null, `VERIFY_TOP_K`, default 5, is used)
- **Response**: `VerifyResponse { case_id, claim, verdict: "supported" | "denied" | "inconclusive", rationale, supporting_quotes: Citation[], denying_quotes: Citation[], retrieved_quotes: Citation[], model, stubbed, duration_ms }` (200 OK)
- **Errors**: `case_not_found` (404), `case_not_ingested` (409), `validation_error` (422), `llm_unavailable` (503), `internal_error` (500)
- **Notes**:
    - Allowed only when the case status is `ingested` or `stale`
    - `inconclusive` is the expected verdict when the retrieved chunks give no support either way
    - `retrieved_quotes` lists every chunk the generator saw
    - Internally the LLM answers with JSON `{ "verdict", "rationale", "supporting_quotes": [{ "index", "quote" }], "denying_quotes": [{ "index", "quote" }] }`, where `index` is the number of the retrieved excerpt and `quote` is copied from it. The legacy `supporting_quote_indices` / `denying_quote_indices` lists are still accepted
    - A quote with an invalid index is attributed to the retrieved chunk that contains it, or dropped if none does
    - Quotes that do not occur in the stored chunk text are kept with `verbatim = false`
    - If the model returns no evidence at all, the top retrieved chunk is attached (as denying for `denied`, otherwise as supporting) so the user always sees the closest excerpt
- **Auth Required**: No (local single-user prototype)

---

## Health Check

### GET /health

- **Description**: Liveness probe, no dependency checks
- **Response**: `{ "status": "ok" }` (200 OK)
- **Auth Required**: No (local single-user prototype)

### GET /

- **Description**: Root endpoint
- **Response**: `{ "service": "Legal Document Assistant API", "version": "0.2.0", "docs": "/docs" }` (200 OK)
- **Notes**: Interactive OpenAPI documentation is served at `/docs`
- **Auth Required**: No (local single-user prototype)

---

## Error Envelope

Every non-2xx response has the same body (`ErrorResponse` in `schemas/common.py`):

```json
{
  "error": {
    "code": "case_not_found",
    "message": "Case not found",
    "details": null
  },
  "request_id": "5f0c6f7e-8c1b-4d0e-9f59-0c7d1b1f2a3b"
}
```

- `error.code`: stable snake_case code; clients branch on it, never on `message`
- `error.message`: human-readable text
- `error.details`: object with extra context or `null` (for `validation_error` it lists the failing fields)
- `request_id`: same value as the `X-Request-ID` response header; it also appears in the server access log

| Code | HTTP Status | Raised by |
| --- | --- | --- |
| `validation_error` | 422 | Any endpoint with a body, path or query parameters that fail validation |
| `case_not_found` | 404 | Every `/cases/{case_id}` endpoint |
| `document_not_found` | 404 | `DELETE /api/v1/cases/{case_id}/documents/{document_id}` |
| `unsupported_media_type` | 415 | Document upload with a suffix other than `.pdf` / `.txt`, a content type that does not match the suffix, or a `.pdf` whose content does not start with `%PDF` |
| `payload_too_large` | 413 | Document upload above `MAX_UPLOAD_MB` |
| `empty_file` | 400 | Document upload with zero bytes |
| `no_documents` | 409 | Ingest on a case without documents |
| `case_not_ingested` | 409 | Summarize or verify on a case with status `empty` or `uploaded` |
| `ingest_failed` | 500 | Ingest when extraction fails, no text can be extracted, or embedding / the vector store fails (existing index kept when extraction fails) |
| `llm_unavailable` | 503 | Summarize or verify when Ollama fails and `OLLAMA_STUB_ON_UNAVAILABLE=false` |
| `internal_error` | 500 | Any unexpected server error (details are logged, not returned) |

---

## Common Schemas

### CaseCreate

```text
title:        string   (required, 1..200 chars)
description:  string   (optional, max 2000 chars)
```

### CaseUpdate

```text
title:        string   (optional, 1..200 chars)
description:  string   (optional, max 2000 chars)
```

### CaseResponse

```text
id:              string (UUID)
title:           string
description:     string | null
created_at:      datetime
updated_at:      datetime
document_count:  int
status:          "empty" | "uploaded" | "ingested" | "stale"
chunk_count:     int
ingested_at:     datetime | null
```

Lifecycle: `empty` (upload) to `uploaded` (ingest) to `ingested`; an upload or document delete on an ingested case gives `stale`; ingest on a stale case gives `ingested` again; deleting the last document gives `empty`.

### DocumentResponse

```text
id:            string (UUID)
case_id:       string (UUID)
filename:      string
content_type:  string   ("application/pdf" or "text/plain")
size_bytes:    int
sha256:        string | null   (hex digest of the uploaded bytes; null only for legacy records)
uploaded_at:   datetime
```

### IngestResponse

```text
case_id:              string (UUID)
documents_processed:  int
chunks_indexed:       int
embedding_backend:    string   ("sentence-transformers" | "ollama" | "hash_stub")
embedding_model:      string
chunk_size:           int
chunk_overlap:        int
vector_store_path:    string
persisted:            bool
duration_ms:          float
```

### IndexStatsResponse

```text
case_id:            string (UUID)
collection:         string   (Chroma collection name of the case)
chunk_count:        int
embedding_backend:  string | null
embedding_model:    string | null
ingested_at:        datetime | null
```

### SummarizeRequest

```text
top_k:  int | null   (optional, 1..20; null or omitted uses SUMMARIZE_TOP_K = 8)
```

### SummarizeResponse

```text
case_id:      string (UUID)
summary:      string   (Bulgarian)
citations:    Citation[]
model:        string   (Ollama tag used, e.g. "qwen2.5:7b")
stubbed:      bool
chunks_used:  int
duration_ms:  float
```

### VerifyRequest

```text
claim:  string   (required, 3..1000 chars)
top_k:  int | null   (optional, 1..20; null or omitted uses VERIFY_TOP_K = 5)
```

### VerifyResponse

```text
case_id:            string (UUID)
claim:              string
verdict:            "supported" | "denied" | "inconclusive"
rationale:          string
supporting_quotes:  Citation[]
denying_quotes:     Citation[]
retrieved_quotes:   Citation[]
model:              string
stubbed:            bool
duration_ms:        float
```

### Citation

```text
document_id:        string (UUID)
document_filename:  string
chunk_id:           string
chunk_index:        int | null
quote:              string   (at most 500 chars when taken from a chunk)
relevance:          float | null
verbatim:           bool
```

- `verbatim` is true when `quote` occurs exactly (case-sensitive) in the stored chunk text after Unicode NFC normalisation, whitespace collapsing and stripping of enclosing quotation marks
- Non-verbatim quotes returned by the LLM are kept but flagged with `verbatim = false`, so the UI can mark them
- When `stubbed = true`, quotes are raw chunk excerpts and `verbatim` is always true

### HealthResponse

```text
status:        "ok" | "degraded"
version:       string
ollama:
  reachable:         bool
  base_url:          string
  model:             string
  model_present:     bool | null
  models_installed:  string[]
embeddings:
  backend:             string
  backend_configured:  string
  model:               string
  device:              string
vector_store:
  path:  string
chunking:
  size:     int
  overlap:  int
```

### Models response (GET /api/v1/models)

```text
active:     string
reachable:  bool
installed:  string[]
```

### ErrorResponse

```text
error:
  code:     string
  message:  string
  details:  object | null
request_id:  string (UUID)
```
