# syntax=docker/dockerfile:1

FROM --platform=$BUILDPLATFORM node:22.12.0-alpine AS ui
WORKDIR /ui
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# Own stage, so a change to requirements.txt doesn't download the model again; tests keep the names in step.
FROM python:3.11.11-slim AS model
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1 HF_HUB_DISABLE_XET=1
RUN pip install fastembed==0.9.1 && mkdir /models && (python -c "from fastembed import TextEmbedding; \
    list(TextEmbedding('sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2', cache_dir='/models').embed(['ok']))" \
    || echo "WARNING: embedding model not downloaded, knowledge base search will use words only")

FROM python:3.11.11-slim AS deps
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
COPY backend/requirements.txt .
RUN python -m venv /venv && /venv/bin/pip install -r requirements.txt

FROM python:3.11.11-slim
ENV PATH=/venv/bin:$PATH PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    FASTEMBED_CACHE_DIR=/app/models HF_HUB_OFFLINE=1
RUN useradd --create-home --uid 10001 app
WORKDIR /app
COPY --from=deps /venv /venv
COPY --from=model --chown=app:app /models ./models
COPY backend/app ./app
COPY --from=ui /ui/dist ./static
USER app
EXPOSE 8080
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
