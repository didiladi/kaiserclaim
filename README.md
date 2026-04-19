# KaiserClaim

> Automated Austrian health insurance expense manager.

Replaces the tedious two-step ÖGK → Merkur reimbursement process with a fully automated, local-first pipeline. Built for home-lab k3s but architected for SaaS from day one.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688.svg)](https://fastapi.tiangolo.com/)

## Status

### Implemented

- [x] Project scaffold — FastAPI app, SQLAlchemy 2.0 async, Pydantic v2 schemas
- [x] Full database model — `User`, `InsuranceContract`, `BenefitRule`, `Invoice`, `BenefitUsage` with UUID PKs and multi-tenant `user_id` on every table
- [x] Alembic async migration setup
- [x] Invoice state machine (`RECEIVED` → ... → `COMPLETED`) with enum types
- [x] OCR engine — `ocrmypdf` + `pypdf` text extraction, German language pack, async-safe
- [x] Pharmacy receipt regex parser — date, total amount, ATU number extraction
- [x] Gemini contract auditor — parses unstructured PDF text into structured `BenefitRule` rows
- [x] Celery task workers — `run_ocr`, `submit_to_merkur`, `submit_to_oegk`, `poll_oegk_refund`
- [x] Playwright bots — `MerkurBot` (headless) and `OegkBot` (persistent context for ID-Austria 2FA)
- [x] REST API — invoice CRUD, contract upload + parse, live benefit quota dashboard endpoint
- [x] Docker Compose local dev stack (Postgres, Redis, API, Worker, auto-migration)
- [x] Kubernetes manifests — Namespace, Secret, PVC, migrate Job, API + Worker Deployments, Traefik IngressRoute, Kustomize overlays
- [x] GitHub Actions CI — builds and pushes API + Worker images to GHCR on push to `main`

### Planned / Not yet implemented

- [ ] **Auth** — JWT middleware replacing the current `user_id` stub in `api/dependencies.py`
- [ ] **File watcher** — inotify/watchdog service to auto-ingest invoices dropped on the NAS
- [ ] **ÖGK full path** — end-to-end test of the `READY_FOR_OEGK → OEGK_REFUNDED` flow
- [ ] **Merkur Playwright selectors** — portal CSS selectors need to be mapped against the live Merkur portal
- [ ] **ÖGK Playwright selectors** — same for the ÖGK portal
- [ ] **Dashboard / frontend** — UI for the Auditor quota view (currently API-only)
- [ ] **Multi-insurance support** — ÖGK + additional private insurers beyond Merkur
- [ ] **Quota reset scheduling** — automatic `reset_date` computation for `BIANNUAL` rules
- [ ] **Hosted SaaS mode** — managed deployment with per-user portal credential vault

## What it does

**Automator** — Watches a NAS folder for invoices (PDF/image). Runs OCR, extracts metadata, submits to ÖGK (semi-automated, ID-Austria 2FA handled once via persistent browser session), polls for the ÖGK refund PDF, then automatically submits everything to Merkur.

**Auditor** — Upload your Merkur contract PDF once. Gemini parses it into structured benefit quota rules (e.g. "150 € Zahnreinigung/year"). As invoices are processed, the dashboard shows how much of each quota remains.

**MVP (Phase 1)** — Pharmacy short-track: pharmacy receipts skip ÖGK entirely and go straight to Merkur.

## Stack

| Layer | Technology |
|---|---|
| API | FastAPI + Uvicorn |
| Database | PostgreSQL 16 + SQLAlchemy 2.0 (asyncpg) + Alembic |
| Task queue | Celery + Redis |
| OCR | ocrmypdf (Tesseract, German language pack) |
| Browser automation | Playwright (Chromium) |
| AI | Google Gemini 1.5 Flash |
| Container runtime | Docker / k3s |

## Project layout

```
kaiserclaim/
├── api/              # FastAPI routers and dependencies
├── alembic/          # Database migrations
├── core/             # Config, database session
├── k8s/              # Kubernetes manifests (Kustomize)
├── models/           # SQLAlchemy ORM models
├── schemas/          # Pydantic v2 request/response schemas
├── services/         # OCR, Gemini, regex extraction
├── workers/          # Celery tasks, Playwright bots
└── main.py           # FastAPI application entry point
```

## Invoice state machine

```
RECEIVED → OCR_PROCESSING → READY_FOR_OEGK → OEGK_SUBMITTED → OEGK_REFUNDED → READY_FOR_MERKUR → MERKUR_SUBMITTED → COMPLETED
                                    ↑
                         Pharmacy short-track starts here (READY_FOR_MERKUR)
```

## Getting started

### Prerequisites

- Docker + Docker Compose
- Python 3.11+ (for local development without Docker)
- A `.env` file (copy from `.env.example`)

### Local development

```bash
cp .env.example .env
# Edit .env — fill in GEMINI_API_KEY, MERKUR_USERNAME, MERKUR_PASSWORD

docker compose up --build
```

The API is available at `http://localhost:8000`. Interactive docs at `http://localhost:8000/docs`.

### Running database migrations

```bash
# Inside Docker (first run is automatic via the migrate service)
docker compose run --rm migrate

# Locally
alembic upgrade head

# Generate a new migration after model changes
alembic revision --autogenerate -m "describe your change"
```

### Running the Celery worker locally

```bash
celery -A workers.tasks.celery_app worker --loglevel=info
```

## Deploying to k3s

```bash
# 1. Push secrets (run once, or whenever credentials change)
kubectl create secret generic kaiserclaim-secrets \
  --from-env-file=.env \
  -n kaiserclaim \
  --dry-run=client -o yaml | kubectl apply -f -

# 2. Apply all manifests
kubectl apply -k k8s/overlays/homelab/

# 3. Run migrations
kubectl apply -f k8s/base/migrate-job.yaml
kubectl wait --for=condition=complete job/kaiserclaim-migrate -n kaiserclaim --timeout=120s

# 4. Check rollout
kubectl rollout status deployment/kaiserclaim-api -n kaiserclaim
```

The API is exposed at `http://kaiserclaim.local` via Traefik (add to your LAN DNS or `/etc/hosts`).

## ÖGK 2FA (ID-Austria)

The ÖGK bot uses a persistent Playwright browser context stored at `STORAGE_ROOT/.oegk_browser_session`. On first run the browser window opens for you to complete the ID-Austria login. Subsequent runs reuse the saved session. The session volume is mounted into the worker pod so it survives restarts.

## Multi-tenancy

Every database table carries a `user_id` column. The architecture is SaaS-ready from day one — the auth stub in `api/dependencies.py` accepts a `user_id` parameter and should be replaced with proper JWT middleware before exposing the service to multiple users.

## Environment variables

| Variable | Description |
|---|---|
| `DATABASE_URL` | asyncpg PostgreSQL connection string |
| `REDIS_URL` | Redis connection string |
| `CELERY_BROKER_URL` | Celery broker (Redis) |
| `CELERY_RESULT_BACKEND` | Celery result backend (Redis) |
| `GEMINI_API_KEY` | Google Gemini API key |
| `STORAGE_ROOT` | NAS mount path inside the container |
| `SECRET_KEY` | App secret (JWT signing, future use) |
| `MERKUR_USERNAME` | Merkur portal login email |
| `MERKUR_PASSWORD` | Merkur portal password |
| `DEBUG` | Enable SQLAlchemy query logging (default: false) |
