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

# Frontend dev server (proxies /api to localhost:8000)
cd frontend && npm run dev           # http://localhost:5173
cd frontend && npm run build         # production build → static/frontend/

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

Pharmacy receipts (MVP) skip ÖGK entirely: `run_ocr` sets status to `READY_FOR_MERKUR` directly.

**Pipeline variant detection** — computed at read time in `schemas/payload.py` (`_derive_pipeline`). If `invoice.category` contains "medikament" or "apotheke" (case-insensitive), the invoice is `pharmacy`; otherwise `standard`. Pharmacy path shows 5 stepper steps in the UI; standard shows all 8.

### Data model overview

| Model | Key fields | Notes |
|---|---|---|
| `User` | `id`, `email` | One user owns everything |
| `FamilyMember` | `user_id`, `member_key`, `name`, `color`, `initials` | `member_key` is a stable slug (`maria`, `thomas`…) used as the filter identifier by the frontend |
| `InsuranceContract` | `user_id`, `provider_name`, `policy_number` | |
| `BenefitRule` | `contract_id`, `benefit_name`, `limit_amount`, `limit_type` | Populated by `services/llm_auditor.py` |
| `Invoice` | `user_id`, `family_member_id`, `category`, `status`, … | `category` is denormalized for display; `family_member_id` FK to `FamilyMember` |
| `BenefitUsage` | `invoice_id`, `benefit_rule_id`, `amount_used` | Appended when invoice reaches COMPLETED |

### API endpoint map

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/v1/invoices/upload` | Upload invoice file → triggers OCR worker |
| GET | `/api/v1/invoices/` | List invoices with `member_key`, `status_group`, `search` filters |
| GET | `/api/v1/invoices/{id}` | Get single invoice |
| POST | `/api/v1/invoices/{id}/submit-merkur` | Manually trigger Merkur submission |
| GET | `/api/v1/contracts/` | List contracts |
| POST | `/api/v1/contracts/{id}/parse-pdf` | Parse contract PDF with Gemini |
| GET | `/api/v1/contracts/{id}/benefits` | Benefit quotas with remaining amounts |
| GET/POST | `/api/v1/family/` | List / create family members |
| GET | `/api/v1/dashboard/summary` | Hero figures: `total_paid`, `total_reimbursed` (82% rule), `in_progress_count`, `eigenanteil`, `benefit_alerts` |
| GET | `/api/v1/stats/monthly` | Monthly aggregations, filtered by `year` and `member_key` |
| GET | `/api/v1/stats/yearly` | Per-year totals |
| GET | `/api/v1/stats/members` | Per-member breakdown with category split |

### Async boundary

The API is fully async (FastAPI + asyncpg). Celery workers are synchronous; they bridge into async code via `asyncio.get_event_loop().run_until_complete()` in `workers/tasks.py`. Do not introduce `await` directly inside Celery task bodies — use the `_run()` helper or extract an `async def` and call `_run()` on it.

### Multi-tenancy

Every table has a `user_id` column. All queries in API endpoints must filter by `current_user.id`. The auth layer in `api/dependencies.py` is a stub (user_id passed as a parameter) — replace with JWT extraction before exposing to multiple users.

### Playwright bots

- `MerkurBot` — fully headless, stateless, safe to run in any pod.
- `OegkBot` — uses `launch_persistent_context()` with the session stored at `STORAGE_ROOT/.oegk_browser_session`. This directory is mounted as a named volume so the ID-Austria 2FA session survives pod restarts. The bot runs `headless=False` and waits up to 3 minutes for the user to complete 2FA when the session has expired.

### Settings

All configuration lives in `core/config.py` (`Settings` via `pydantic-settings`). Values are read from `.env`. `get_settings()` is `@lru_cache`'d — in tests, clear the cache with `get_settings.cache_clear()` before overriding env vars. The Alembic `env.py` pulls `DATABASE_URL` from `Settings` directly, so `.env` is the single source of truth.

---

## Frontend

**Stack:** Vite + React 18 + TypeScript + Tailwind CSS 3, Plus Jakarta Sans, lucide-react (icons), clsx.

**Dev:** `cd frontend && npm run dev` → `http://localhost:5173`. Vite proxies `/api` to `http://localhost:8000` (configured in `vite.config.ts`).

**Design spec:** `design_handoff_kaiserclaim/README.md` is the canonical pixel-accurate reference. The JSX files in that directory are interactive prototypes — match them visually.

### Folder layout

```
frontend/src/
├── api.ts              # All API calls; USER_ID constant at top
├── App.tsx             # BrowserRouter + AppProvider + routes
├── index.css           # Tailwind directives + global keyframes
├── lib/
│   ├── format.ts       # de-AT EUR formatter, DD.MM.YYYY, relativeTime
│   ├── pipeline.ts     # getPipelineSteps, getCurrentStepIndex — status→step mapping
│   └── tokens.ts       # STATUS_CONFIG colors, MEMBER_COLORS, BENEFIT_CATEGORIES
├── components/         # Shared UI: AppShell, TopBar, BottomNav, InvoiceCard, …
├── state/
│   └── AppContext.tsx  # activeMember, familyMembers, loggedIn — global state
└── pages/              # One file per route (Login, Home, Upload, …)
```

### Routing

| Path | Screen | Bottom nav | Back arrow |
|---|---|---|---|
| `/login` | Login | no | no |
| `/` | Home (Übersicht) | yes | no |
| `/invoices` | Belege list | yes | no |
| `/invoices/:id` | Beleg-Detail | no | yes |
| `/upload` | Upload | no | yes |
| `/benefits` | Leistungen | yes | no |
| `/stats` | Statistiken | yes | no |
| `/onboarding` | Vertrag hinzufügen | no | yes |
| `/settings` | Einstellungen | no | no |

### Adding a new screen

1. Create `frontend/src/pages/ScreenName.tsx` — export a named function.
2. Import and add a `<Route path="/path" element={<ScreenName />} />` inside the `<AppShell>` block in `App.tsx`.
3. If it's a sub-screen (back arrow, no bottom nav), add its path to the relevant arrays in `components/AppShell.tsx`.
4. If it needs family filtering, render `<FamilyFilterPills />` at the top and read `activeMember` from `useAppContext()`.

---

## Adding a new model

1. Add the SQLAlchemy class to `models/domain.py` with a `user_id` FK.
2. Add Pydantic `Create` / `Read` schemas to `schemas/payload.py`.
3. Run `alembic revision --autogenerate -m "add <model>"` — review the generated file before applying.
4. Import the model in `alembic/env.py` (it already imports `Base` from `models/domain`; just ensure the class is defined there).

---

## Merkur portal selector calibration

All selectors in `MerkurBot._submit` (`workers/playwright_bot.py`) must be validated against
the live Merkur portal before the first real submission. Run the calibration harness once:

```bash
# requires a display (headed browser) and .env credentials
playwright install chromium
python scripts/calibrate_merkur.py [--receipt path/to/receipt.pdf]
```

The harness walks through the full submission flow, stops before the final submit, and
prints which candidate selectors matched. Raw HTML snapshots land in `scripts/.merkur_capture/`
(gitignored — may contain PII).

After calibration:
1. Update selectors in `workers/playwright_bot.py` with the confirmed values.
2. Strip PII from the snapshots (name, policy number, address).
3. Copy sanitized HTML to `tests/fixtures/merkur/` and commit.
4. Run `pytest tests/test_merkur_bot.py` — selector assertions must pass before any selector change is merged.
