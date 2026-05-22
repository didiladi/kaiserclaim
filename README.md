# KaiserClaim

> Automated Austrian health insurance expense manager.

Replaces the tedious two-step ÖGK → Merkur reimbursement process with a fully automated, local-first pipeline. Mobile-first PWA frontend, FastAPI backend, Celery workers. Built for home-lab k3s but architected for SaaS from day one.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688.svg)](https://fastapi.tiangolo.com/)

## Status

### Implemented

- [x] Project scaffold — FastAPI app, SQLAlchemy 2.0 async, Pydantic v2 schemas
- [x] Full database model — `User`, `FamilyMember`, `InsuranceContract`, `BenefitRule`, `Invoice`, `BenefitUsage`
- [x] Alembic async migration setup (migrations 0001–0003)
- [x] Invoice state machine (`RECEIVED` → ... → `COMPLETED`) with enum types
- [x] OCR engine — `ocrmypdf` + `pypdf` text extraction, German language pack, async-safe
- [x] Pharmacy receipt regex parser — date, total amount, ATU number extraction
- [x] Gemini contract auditor — parses unstructured PDF text into structured `BenefitRule` rows
- [x] Celery task workers — `run_ocr`, `submit_to_merkur`, `submit_to_oegk`, `poll_oegk_refund`
- [x] Playwright bots — `MerkurBot` (headless) and `OegkBot` (persistent context for ID-Austria 2FA)
- [x] REST API — invoice CRUD, contract upload + parse, benefit quota endpoints, family members, dashboard summary, statistics aggregations
- [x] Docker Compose local dev stack (Postgres, Redis, API, Worker, auto-migration)
- [x] Kubernetes manifests — Namespace, Secret, PVC, migrate Job, API + Worker Deployments, Traefik IngressRoute, Kustomize overlays
- [x] GitHub Actions CI — builds and pushes API + Worker images to GHCR on push to `main`
- [x] **Mobile-first PWA frontend** — full 9-screen UI (Login, Home, Belege, Upload, Detail, Leistungen, Statistiken, Onboarding, Einstellungen)

### Deferred — UI shell present, backend stub

These screens exist in the frontend and are fully interactive, but the backend implementation is not complete:

- **Auth** — The login screen renders and navigates, but calls no backend endpoint. The `user_id` in `api/dependencies.py` is still a constant. Replace with JWT middleware (`api/dependencies.py`) before exposing to multiple users.
- **Portal credential vault** — Settings shows "hinterlegt" indicators for ÖGK and Merkur portals. The AES-256 encrypted storage table is not yet implemented.
- **PWA manifest / service worker** — App runs as a mobile web app but is not installable as a PWA yet.

### Planned / not started

- [ ] **File watcher** — inotify/watchdog service to auto-ingest invoices dropped on the NAS
- [ ] **ÖGK full path** — end-to-end test of the `READY_FOR_OEGK → OEGK_REFUNDED` flow with live ÖGK portal selectors
- [ ] **Quota reset scheduling** — automatic `reset_date` computation for `BIANNUAL` rules
- [ ] **Dark mode** — tokens defined in design system; toggle not yet wired
- [ ] **Hosted SaaS mode** — managed deployment with per-user portal credential vault

---

## What it does

**Automator** — Photograph or PDF a medical/pharmacy receipt. The app runs OCR, extracts amount and date, submits to ÖGK (semi-automated, ID-Austria 2FA handled once via persistent browser session), polls for the ÖGK refund, then automatically submits to Merkur.

**Auditor** — Upload your Merkur contract PDF once. Gemini parses it into structured benefit quota rules (e.g. "150 € Zahnreinigung/jährlich"). As invoices are processed, the Leistungen screen shows how much of each quota remains — per family member.

**MVP (Phase 1)** — Pharmacy short-track: pharmacy receipts skip ÖGK entirely and go straight to Merkur (5-step pipeline instead of 8).

---

## Stack

| Layer | Technology |
|---|---|
| API | FastAPI + Uvicorn |
| Database | PostgreSQL 16 + SQLAlchemy 2.0 (asyncpg) + Alembic |
| Task queue | Celery + Redis |
| OCR | ocrmypdf (Tesseract, German language pack) |
| Browser automation | Playwright (Chromium) |
| AI | Google Gemini 1.5 Flash |
| **Frontend** | **Vite + React 18 + TypeScript + Tailwind CSS 3** |
| Container runtime | Docker / k3s |

---

## Project layout

```
kaiserclaim/
├── api/                    # FastAPI routers and dependencies
│   └── endpoints/          # invoices, contracts, family, stats, webhooks
├── alembic/                # Database migrations (0001–0003)
├── core/                   # Config, database session
├── design_handoff_kaiserclaim/  # Design spec (README.md + prototype JSX)
├── frontend/               # Vite+React PWA
│   └── src/
│       ├── api.ts          # All API calls
│       ├── App.tsx         # Router + AppProvider
│       ├── components/     # AppShell, InvoiceCard, Stepper, ProgressBar, …
│       ├── lib/            # format.ts, pipeline.ts, tokens.ts
│       ├── pages/          # One file per route
│       └── state/          # AppContext (activeMember, familyMembers, loggedIn)
├── k8s/                    # Kubernetes manifests (Kustomize)
├── models/                 # SQLAlchemy ORM models
├── schemas/                # Pydantic v2 request/response schemas
├── services/               # OCR, Gemini, regex extraction
├── workers/                # Celery tasks, Playwright bots
└── main.py                 # FastAPI application entry point
```

---

## Invoice state machine

```
RECEIVED → OCR_PROCESSING → READY_FOR_OEGK → OEGK_SUBMITTED → OEGK_REFUNDED → READY_FOR_MERKUR → MERKUR_SUBMITTED → COMPLETED
                                    ↑
                         Pharmacy short-track enters here (READY_FOR_MERKUR)
```

Pipeline variant is derived at read time from `invoice.category`: if the category contains "medikament" or "apotheke" (case-insensitive), it's the 5-step pharmacy path; otherwise the full 8-step standard path.

---

## Getting started

### Prerequisites

- Docker + Docker Compose
- Node.js 20+ (for frontend development)
- A `.env` file (copy from `.env.example`)

### Local development

```bash
cp .env.example .env
# Fill in GEMINI_API_KEY, MERKUR_USERNAME, MERKUR_PASSWORD

# Start the full backend stack
docker compose up --build
# API: http://localhost:8000  Docs: http://localhost:8000/docs

# In a separate terminal — start the frontend dev server
cd frontend && npm install && npm run dev
# App: http://localhost:5173
```

The Vite dev server proxies `/api` to `http://localhost:8000` automatically.

### Seeding family members

There are no family members in a fresh database. Add them via the API:

```bash
curl -X POST "http://localhost:8000/api/v1/family/?user_id=00000000-0000-0000-0000-000000000001" \
  -H "Content-Type: application/json" \
  -d '{"member_key":"maria","name":"Maria Mustermann","color":"#E84393","initials":"MM"}'
```

### Running database migrations

```bash
# Inside Docker (first run is automatic via the migrate service)
docker compose run --rm migrate

# Locally
alembic upgrade head

# Generate a new migration after model changes
alembic revision --autogenerate -m "describe your change"
```

### Building the frontend for production

```bash
cd frontend && npm run build
# Output: frontend/dist/  — copy to static/frontend/ to serve via FastAPI
```

---

## Deploying to k3s

```bash
# 1. Push secrets
kubectl create secret generic kaiserclaim-secrets \
  --from-env-file=.env \
  -n kaiserclaim \
  --dry-run=client -o yaml | kubectl apply -f -

# 2. Apply manifests
kubectl apply -k k8s/overlays/homelab/

# 3. Run migrations
kubectl apply -f k8s/base/migrate-job.yaml
kubectl wait --for=condition=complete job/kaiserclaim-migrate -n kaiserclaim --timeout=120s

# 4. Check rollout
kubectl rollout status deployment/kaiserclaim-api -n kaiserclaim
```

The API is exposed at `http://kaiserclaim.local` via Traefik (add to your LAN DNS or `/etc/hosts`).

---

## Merkur dry run

Before the first real submission, verify the full wizard flow without filing a claim:

```bash
playwright install chromium   # once
python scripts/dry_run_merkur.py \
    --receipt /path/to/receipt.pdf \
    --patient "Name substring" \
    --iban AT232081500044776086
```

---

## ÖGK 2FA (ID-Austria)

The ÖGK bot uses a persistent Playwright browser context stored at `STORAGE_ROOT/.oegk_browser_session`. On first run the browser window opens for you to complete the ID-Austria login. Subsequent runs reuse the saved session. The session volume is mounted into the worker pod so it survives restarts.

---

## Design reference

The `design_handoff_kaiserclaim/` directory contains the pixel-accurate design spec:

- `README.md` — design tokens, component specs, screen-by-screen layout, data models, animation timings
- `KaiserClaim.html` — interactive prototype (open in browser to see all screens)
- `kc-*.jsx` — prototype React components (reference only; not used in production)

When making UI changes, compare against the prototype at 390×844px viewport (Chrome DevTools mobile mode).

---

## Multi-tenancy

Every database table carries a `user_id` column. The architecture is SaaS-ready — the auth stub in `api/dependencies.py` accepts a `user_id` query parameter and should be replaced with proper JWT middleware before exposing the service to multiple users.

---

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
| `MERKUR_BANK_IBAN` | IBAN to select for reimbursement transfers (no spaces) |
| `DEBUG` | Enable SQLAlchemy query logging (default: false) |
