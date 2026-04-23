# -------------------------------------------------------------------
# Frontend build
# -------------------------------------------------------------------
FROM node:20-alpine AS frontend-build
WORKDIR /frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ .
RUN npm run build

# -------------------------------------------------------------------
# Python base
# -------------------------------------------------------------------
FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    ghostscript \
    img2pdf \
    libffi-dev \
    pngquant \
    tesseract-ocr \
    tesseract-ocr-deu \
    unpaper \
    libzbar0 \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libgbm1 \
    libxkbcommon0 \
    libasound2 \
    libatspi2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# Install Playwright browser binaries (Chromium only)
RUN playwright install chromium

COPY . .

# Embed the built frontend so the API can serve it
COPY --from=frontend-build /frontend/dist ./static/frontend

# -------------------------------------------------------------------
# API target
# -------------------------------------------------------------------
FROM base AS api
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

# -------------------------------------------------------------------
# Worker target
# -------------------------------------------------------------------
FROM base AS worker
CMD ["celery", "-A", "workers.tasks.celery_app", "worker", "--loglevel=info", "--concurrency=2"]
