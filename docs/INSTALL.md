# Installation Guide

Step-by-step instructions for setting up the Legal Document Assistant on **macOS** and **Linux**. The system runs entirely on the local machine.

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Clone the Repository](#2-clone-the-repository)
3. [Install Ollama](#3-install-ollama)
4. [Pull Models](#4-pull-models)
5. [Backend Setup](#5-backend-setup)
6. [Frontend Setup](#6-frontend-setup)
7. [Environment Configuration](#7-environment-configuration)
8. [Running the Application](#8-running-the-application)
9. [Docker Compose (Alternative)](#9-docker-compose-alternative)
10. [Troubleshooting](#10-troubleshooting)

---

## 1. Prerequisites

| Requirement | Minimum | Recommended |
|-------------|---------|-------------|
| Python | 3.12 | 3.13 |
| Node.js | 20.19 | 22.x |
| RAM | 8 GB (qwen2.5:7b) | 16 GB (BgGPT v1.0 9B) |
| Disk | 15 GB free | 25 GB free (models + data) |
| OS | macOS 13+ / Ubuntu 22.04+ | macOS 14+ / Ubuntu 24.04 |

---

## 2. Clone the Repository

```bash
git clone <repository-url>
cd legal
```

---

## 3. Install Ollama

### macOS

Download and install from [ollama.com](https://ollama.com) or use Homebrew:

```bash
brew install ollama
```

### Linux (Ubuntu / Debian)

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

### Start the Ollama server

```bash
ollama serve
```

The server listens on `http://127.0.0.1:11434` by default. Keep this terminal open.

---

## 4. Pull Models

In a separate terminal, pull the default model:

```bash
# Default: BgGPT v1.0 9B (about 5.8 GB download, about 7.7 GB loaded)
ollama pull s_emanuilov/BgGPT-v1.0:9b

# Low-memory fallback (about 4.7 GB download, about 4.9 GB loaded)
ollama pull qwen2.5:7b
```

For evaluation runs, also pull the control model:

```bash
ollama pull llama3.1:8b
```

Verify:

```bash
ollama list
```

---

## 5. Backend Setup

```bash
cd backend

# Create and activate a virtual environment (Python 3.13 recommended)
python3.13 -m venv .venv
source .venv/bin/activate   # macOS / Linux

# Install CPU-only PyTorch (saves disk and avoids CUDA dependency)
pip install --index-url https://download.pytorch.org/whl/cpu torch

# Install all dependencies (production + development)
pip install -r requirements-dev.txt
```

### Verify

```bash
# Run tests (uses hash_stub embeddings and mocked Ollama, no network needed)
pytest -q

# Lint
ruff check . && ruff format --check .
```

---

## 6. Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Lint
npm run lint

# Type check (optional)
npm run typecheck

# Build for production (optional, dev server is sufficient for development)
npm run build
```

---

## 7. Environment Configuration

Copy the example config:

```bash
cp .env.example .env
```

Key settings (edit `.env` as needed):

| Variable | Default | Description |
|----------|---------|-------------|
| `OLLAMA_MODEL` | `s_emanuilov/BgGPT-v1.0:9b` | Active generation model |
| `OLLAMA_BASE_URL` | `http://127.0.0.1:11434` | Ollama HTTP API |
| `OLLAMA_NUM_CTX` | `4096` | Context window (higher = more memory) |
| `OLLAMA_STUB_ON_UNAVAILABLE` | `true` | Return stub answers when Ollama is down |
| `EMBEDDING_BACKEND` | `sentence-transformers` | `sentence-transformers`, `ollama` or `hash_stub` |
| `EMBEDDING_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` | Embedding model |
| `CHUNK_SIZE` | `800` | Characters per chunk |
| `CHUNK_OVERLAP` | `120` | Overlap between chunks |
| `MAX_UPLOAD_MB` | `20` | Upload size limit |
| `MODEL_ROUTING` | `off` | `off` or `language` (pick model by document language) |
| `OLLAMA_MODEL_BG` | `s_emanuilov/BgGPT-v1.0:9b` | Model for Bulgarian (when routing=language) |
| `OLLAMA_MODEL_EN` | `qwen2.5:7b` | Model for English (when routing=language) |

### Low-memory machines (≤ 16 GB)

```bash
# Use the smaller model as default
OLLAMA_MODEL=qwen2.5:7b
```

### Language-based model routing (optional)

```bash
MODEL_ROUTING=language
OLLAMA_MODEL_BG=s_emanuilov/BgGPT-v1.0:9b
OLLAMA_MODEL_EN=qwen2.5:7b
```

When routing is active, the two models are loaded alternately. Set
`OLLAMA_MAX_LOADED_MODELS=1` in the Ollama server environment so it unloads
the previous model before loading the next one (saves RAM).

---

## 8. Running the Application

### Terminal 1: Ollama

```bash
ollama serve
```

### Terminal 2: Backend

```bash
cd backend
source .venv/bin/activate
cd ..
PYTHONPATH=backend backend/.venv/bin/python -m uvicorn app.main:app \
  --app-dir backend --host 127.0.0.1 --port 8000 --reload --no-access-log
```

### Terminal 3: Frontend

```bash
cd frontend
npm run dev
```

### Access

| URL | Description |
|-----|-------------|
| `http://127.0.0.1:5173` | Web UI (Vite dev server proxies `/api` to port 8000) |
| `http://127.0.0.1:8000/docs` | Interactive API documentation (Swagger UI) |
| `http://127.0.0.1:8000/api/v1/health` | Health check (Ollama, embeddings, vector store) |

### Quick smoke test

```bash
# Liveness
curl -s http://127.0.0.1:8000/health
# → {"status":"ok"}

# Full health
curl -s http://127.0.0.1:8000/api/v1/health | python3 -m json.tool

# Models
curl -s http://127.0.0.1:8000/api/v1/models | python3 -m json.tool
```

---

## 9. Docker Compose (Alternative)

For a containerised setup with no manual Python/Node installation:

```bash
docker compose up --build
docker compose exec ollama ollama pull s_emanuilov/BgGPT-v1.0:9b
```

| Service | URL | Notes |
|---------|-----|-------|
| frontend | `http://localhost:8080` | nginx, proxies `/api` to backend |
| backend | `http://localhost:8000/docs` | CPU-only image, MiniLM baked in |
| ollama | `http://localhost:11434` | models in the `ollama` volume |

Override settings via shell environment or a root `.env` read by Compose:

```bash
OLLAMA_MODEL=qwen2.5:7b docker compose up
```

---

## 10. Troubleshooting

### Ollama is unreachable

**Symptom:** `/api/v1/health` returns `"status": "degraded"`, `"reachable": false`.

**Fix:**
1. Make sure `ollama serve` is running in a separate terminal.
2. Check that `OLLAMA_BASE_URL` points to the correct address (default `http://127.0.0.1:11434`).
3. Test directly: `curl http://127.0.0.1:11434/api/tags`.

**Note:** When Ollama is down and `OLLAMA_STUB_ON_UNAVAILABLE=true` (default), summarize, verify and ask still return responses flagged with `stubbed: true` — the citations are direct chunk excerpts, not model-generated.

### Model not pulled

**Symptom:** `/api/v1/health` returns `"model_present": false`.

**Fix:**
```bash
ollama pull s_emanuilov/BgGPT-v1.0:9b
# or for low-memory:
ollama pull qwen2.5:7b
```

### Out of memory

**Symptom:** Ollama crashes or the system becomes unresponsive during generation.

**Fix:**
1. Use the smaller model: `OLLAMA_MODEL=qwen2.5:7b` (about 4.9 GB vs 7.7 GB).
2. Reduce context window: `OLLAMA_NUM_CTX=2048`.
3. Close other heavy applications.
4. If using language routing, set `OLLAMA_MAX_LOADED_MODELS=1` in the Ollama server environment.

### Ingest fails

**Symptom:** `ingest_failed` error when indexing documents.

**Fix:**
1. Make sure the document is a valid TXT or PDF file.
2. For PDF: the file must start with `%PDF` and contain extractable text (not a scanned image).
3. Check disk space — the vector store needs room to persist.

### Frontend cannot reach the backend

**Symptom:** The UI shows "API е недостъпен".

**Fix:**
1. Make sure the backend is running on port 8000.
2. Check that `CORS_ORIGINS` includes `http://localhost:5173` (the default).
3. Run the backend from the repository root so `./data` and `.env` resolve correctly.

### Embedding backend falls back to hash_stub

**Symptom:** `/api/v1/health` shows `backend: "hash_stub"` but `backend_configured: "sentence-transformers"`.

**Fix:**
1. Ensure `torch` and `sentence-transformers` are installed in the virtual environment.
2. For CPU-only machines: `pip install --index-url https://download.pytorch.org/whl/cpu torch`.
3. Check that the model `sentence-transformers/all-MiniLM-L6-v2` is downloadable (first run needs internet).

### Tests fail

```bash
cd backend
source .venv/bin/activate
pip install -r requirements-dev.txt   # ensure all test deps
pytest -q                             # hash_stub embeddings, mocked Ollama
ruff check . && ruff format --check . # lint
```
