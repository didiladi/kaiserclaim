# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Local dev stack (Postgres + Redis + API + Worker, migrations run automatically)
docker compose up --build

# Run the API without Docker
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Run the Celery worker without Docker
celery -A workers.tasks.celery_app worker --loglevel=info

# Database migrations
alembic upgrade head
alembic revision --autogenerate -m "describe change"
alembic downgrade -1

# Deploy to k3s
kubectl apply -k k8s/overlays/homelab/
kubectl apply -f k8s/base/migrate-job.yaml
```

## Architecture

KaiserClaim has two distinct concerns that share the same data layer:

**Automator** — a state-machine pipeline driven by Celery tasks. When an invoice is created via `POST /api/v1/invoices/`, the API immediately dispatches `run_ocr` to Celery and returns. All subsequent state transitions happen asynchronously in `workers/tasks.py`. The API surface for state changes is minimal by design: one endpoint to create, one to manually trigger Merkur submission; everything else is driven by the worker.

**Auditor** — a query-time computation. `BenefitRule` rows are populated once by `services/llm_auditor.py` (Gemini parses the contract PDF). `BenefitUsage` rows are appended as invoices complete. Remaining quota is never stored — it's computed as `limit_amount - SUM(amount_used)` in `GET /api/v1/contracts/{id}/benefits`.

### Invoice state machine

```
RECEIVED → OCR_PROCESSING → READY_FOR_OEGK → OEGK_SUBMITTED → OEGK_REFUNDED ↘
                                                                                 READY_FOR_MERKUR → MERKUR_SUBMITTED → COMPLETED
                                    ↑ Pharmacy MVP enters here directly ────────────────────────────────────────────────────┘
```

Pharmacy receipts (MVP) skip ÖGK entirely: `run_ocr` sets status to `READY_FOR_MERKUR` directly. The full ÖGK path (`submit_to_oegk` → `poll_oegk_refund`) is wired but not triggered from the pharmacy flow.

### Async boundary

The API is fully async (FastAPI + asyncpg). Celery workers are synchronous; they bridge into async code via `asyncio.get_event_loop().run_until_complete()` in `workers/tasks.py`. Do not introduce `await` directly inside Celery task bodies — use the `_run()` helper or extract an `async def` and call `_run()` on it.

### Multi-tenancy

Every table has a `user_id` column. All queries in API endpoints must filter by `current_user.id`. The auth layer in `api/dependencies.py` is a stub (user_id passed as a parameter) — replace with JWT extraction before exposing to multiple users.

### Playwright bots

- `MerkurBot` — fully headless, stateless, safe to run in any pod.
- `OegkBot` — uses `launch_persistent_context()` with the session stored at `STORAGE_ROOT/.oegk_browser_session`. This directory is mounted as a named volume so the ID-Austria 2FA session survives pod restarts. The bot runs `headless=False` and waits up to 3 minutes for the user to complete 2FA when the session has expired.

### Settings

All configuration lives in `core/config.py` (`Settings` via `pydantic-settings`). Values are read from `.env`. `get_settings()` is `@lru_cache`'d — in tests, clear the cache with `get_settings.cache_clear()` before overriding env vars. The Alembic `env.py` pulls `DATABASE_URL` from `Settings` directly, so `.env` is the single source of truth.

### Adding a new model

1. Add the SQLAlchemy class to `models/domain.py` with a `user_id` FK.
2. Add Pydantic `Create` / `Read` schemas to `schemas/payload.py`.
3. Run `alembic revision --autogenerate -m "add <model>"` — review the generated file before applying.
4. Import the model in `alembic/env.py` (it already imports `Base` from `models/domain`; just ensure the class is defined there).
