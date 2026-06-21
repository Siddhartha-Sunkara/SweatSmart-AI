# syntax=docker/dockerfile:1.7
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HF_HOME=/cache/huggingface \
    TRANSFORMERS_CACHE=/cache/huggingface \
    SENTENCE_TRANSFORMERS_HOME=/cache/huggingface

# System deps:
#   - build-essential / gcc: native wheels for some ML deps
#   - libgomp1: required by onnxruntime / sentence-transformers
#   - curl: HEALTHCHECK
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
        build-essential \
        gcc \
        libgomp1 \
        curl \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first for layer caching
COPY requirements.txt ./
RUN pip install -r requirements.txt

# Copy the project
COPY api ./api
COPY intent_agent ./intent_agent
COPY workout_planner_agent ./workout_planner_agent
COPY rag ./rag
COPY scripts ./scripts
COPY data ./data

# HuggingFace cache volume (model downloaded lazily on first request)
RUN mkdir -p /cache/huggingface
VOLUME ["/cache/huggingface"]

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/api/health || exit 1

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
