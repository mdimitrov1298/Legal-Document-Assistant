# Build from the repository root so the eval package is available in the image:
#   docker build -f backend/Dockerfile -t legal-backend .
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

ARG TORCH_INDEX_URL=https://download.pytorch.org/whl/cpu
ARG PRELOAD_EMBEDDINGS=true
ARG EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2

RUN useradd --create-home --uid 1000 app \
    && mkdir -p /data /app \
    && chown app:app /data /app

WORKDIR /app/backend

# CPU-only torch keeps the image small and avoids CUDA wheels on 16 GB machines
COPY backend/requirements.txt ./requirements.txt
RUN pip install --index-url "${TORCH_INDEX_URL}" torch \
    && pip install --extra-index-url "${TORCH_INDEX_URL}" -r requirements.txt

COPY --chown=app:app backend/app ./app
COPY --chown=app:app eval /app/eval

USER app

ENV HF_HOME=/home/app/.cache/huggingface \
    APP_ENV=production \
    DATA_DIR=/data \
    CHROMA_PATH=/data/chroma \
    UPLOAD_DIR=/data/uploads \
    EMBEDDING_MODEL=${EMBEDDING_MODEL}

# Bake the embedding model into the image so ingest works offline
RUN if [ "${PRELOAD_EMBEDDINGS}" = "true" ]; then \
      python -c "from sentence_transformers import SentenceTransformer as S; S('${EMBEDDING_MODEL}', device='cpu')"; \
    fi

VOLUME ["/data"]
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
