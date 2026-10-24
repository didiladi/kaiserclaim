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
RECEIVED → OCR_PROCESSING ─┬→ READY_FOR_OEGK → OEGK_SUBMITTING → OEGK_SUBMITTED ─(refund PDF)─┐
                           │                                                                 ↓
                           └→ READY_FOR_MERKUR ←─────────────────────────────────────────────┘
READY_FOR_MERKUR → MERKUR_SUBMITTING → MERKUR_SUBMITTED → MERKUR_REIMBURSED / MERKUR_REJECTED → COMPLETED
OCR finds no amount/date → NEEDS_REVIEW (fix via PATCH /invoices/{id}); any failure past a submit claim → FAILED
```

**Routing** (`first_submission_status` in `schemas/payload.py`): an invoice with an explicit non-pharmacy category goes to `READY_FOR_OEGK`; pharmacy or uncategorised goes straight to `READY_FOR_MERKUR`. Submissions are user-triggered (`/submit-oegk`, `/submit-merkur`). Both claim the invoice with an atomic `READY_* → *_SUBMITTING` transition before touching the portal and never auto-retry after the claim (the click may already have gone through), so a stuck `FAILED` must be reconciled against the real portal by hand.

**ÖGK refunds** (meine ÖGK): `poll_oegk_refunds` (beat, 09:00, cluster) queues one `sync_oegk_refunds(user_id)` per user with invoices waiting on ÖGK (`READY_FOR_OEGK`, `OEGK_SUBMITTING`, `OEGK_SUBMITTED`, `FAILED`; the task expires after 20 h). The sync runs on the `oegk` queue (the cluster worker never consumes it) because `OegkBot` is headed for ID-Austria 2FA: run `scripts/run_oegk_worker.sh` on the desktop. `OegkBot.download_refunds` downloads every PDF in "Eingereichte Rechnungen", and each is sent to `POST /oegk/refund-pdfs` (via `API_BASE_URL`; without it the worker ingests directly, for single-host dev). The cluster owns the files because the Merkur upload reads them. `services/oegk_ingest.py` parses the PDF (`services/oegk_result_parser.py`), dedupes it (no case number: `OegkDocument.dedupe_key` hashes patient, doctor, dates and amounts), and matches an invoice on **patient + treatment day (Vienna) within the PDF's service range + invoice amount**; the patient is the `FamilyMember.svnr` when stored, else a name check. Exactly one match: the PDF becomes an `InvoiceAttachment` (`oegk_refund`) and the invoice jumps to `READY_FOR_MERKUR`. Zero or several matches: the PDF is stored, a notification fires once, and it is retried on every sync (it links as soon as the invoice exists). `submit_to_merkur` uploads the invoice's own file plus all attachments in one Vorgang and checks that every file exists *before* claiming the invoice.

**ÖGK submission is switched off** (`OEGK_SUBMIT_ENABLED`, default false): `POST /invoices/{id}/submit-oegk` returns 501 and `submit_to_oegk` is a no-op, because the meine ÖGK submit flow is not calibrated (see "meine ÖGK calibration status"). The interim path is to submit by hand in meine ÖGK and move the invoice to `OEGK_SUBMITTED` with the "Als bei ÖGK eingereicht markieren" button on the invoice detail page (`PATCH /invoices/{id}/status`); refunds are matched automatically, and unconfirmed `READY_FOR_OEGK` invoices are matched too.

Pharmacy receipts (MVP) skip ÖGK entirely: `run_ocr` sets status to `READY_FOR_MERKUR` directly.

**API response fields**: `InvoiceRead` derives `pipeline`, `current_step`, `reimbursed_amount`, `result_state` and `oegk_reimbursed_amount` in a `model_validator(mode="before")`. Do not go back to overriding `model_validate`: FastAPI validates responses through a TypeAdapter and never calls it (that silently left every field at its default). Endpoints that return invoices must eager-load `merkur_document` and `oegk_document`.

**Pipeline variant detection** — computed at read time in `schemas/payload.py` (`_derive_pipeline`). If `invoice.category` contains "medikament" or "apotheke" (case-insensitive), the invoice is `pharmacy`; otherwise `standard`. Pharmacy path shows 5 stepper steps in the UI; standard shows all 8.

### Data model overview

| Model | Key fields | Notes |
|---|---|---|
| `User` | `id`, `email` | One user owns everything |
| `FamilyMember` | `user_id`, `member_key`, `name`, `color`, `initials`, `svnr` | `member_key` is a stable slug (`maria`, `thomas`…) used as the filter identifier by the frontend. `svnr` (10-digit Sozialversicherungsnummer) is write-only PII: the API only returns `has_svnr`; never log it or put it in fixtures |
| `InsuranceContract` | `user_id`, `provider_name`, `policy_number` | |
| `BenefitRule` | `contract_id`, `benefit_name`, `limit_amount`, `limit_type` | Populated by `services/llm_auditor.py` |
| `Invoice` | `user_id`, `family_member_id`, `category`, `status`, … | `category` is denormalized for display; `family_member_id` FK to `FamilyMember` |
| `BenefitUsage` | `invoice_id`, `benefit_rule_id`, `amount_used` | Appended when invoice reaches COMPLETED |
| `OegkDocument` | `user_id`, `dedupe_key` (unique), `file_path`, `invoice_id`, amounts, dates | A meine ÖGK refund PDF. No raw text is stored (the PDF holds IBAN and address) |
| `InvoiceAttachment` | `invoice_id`, `kind`, `file_path` | Extra files uploaded to Merkur with the invoice's own file (`oegk_refund`) |

### API endpoint map

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/v1/invoices/upload` | Upload invoice file → triggers OCR worker |
| GET | `/api/v1/invoices/` | List invoices with `member_key`, `status_group`, `search`, `pipeline` filters |
| GET | `/api/v1/invoices/{id}` | Get single invoice |
| PATCH | `/api/v1/invoices/{id}` | Correct amount/date/provider/patient (NEEDS_REVIEW recovery) |
| POST | `/api/v1/invoices/{id}/submit-oegk` | Queue ÖGK submission (READY_FOR_OEGK only). 501 while `OEGK_SUBMIT_ENABLED` is off |
| POST | `/api/v1/oegk/refund-pdfs` | Desktop ÖGK worker uploads one refund PDF: store, dedupe, match, attach (`outcome`: linked / unmatched / ambiguous / duplicate / not_a_refund) |
| PATCH | `/api/v1/family/{id}` | Set or clear a member's `svnr` |
| POST | `/api/v1/invoices/{id}/submit-merkur` | Manually trigger Merkur submission |
| GET | `/api/v1/contracts/` | List contracts |
| POST | `/api/v1/contracts/{id}/parse-pdf` | Parse contract PDF with Gemini |
| GET | `/api/v1/contracts/{id}/benefits` | Benefit quotas with remaining amounts |
| GET/POST | `/api/v1/family/` | List / create family members |
| GET | `/api/v1/dashboard/summary` | Hero figures, filterable by `member_key` and `pipeline` (`standard` = doctors, `pharmacy`). Refunds add up from two sources: `oegk_refunded` (real, from the linked ÖGK PDF, counted as soon as it is matched) and Merkur (`merkur_refunded` confirmed, plus an estimate of 82% of the invoice minus the ÖGK part where no Merkur result is linked yet). `total_reimbursed` = both, `eigenanteil` = settled invoices only. `claimed_amount` = invoice totals submitted to ÖGK or Merkur, `claimed_open_amount` = of those still undecided, `not_yet_claimed_amount` = not submitted anywhere yet (`pending_amount` = open + not yet claimed). Also `in_progress_count`, `needs_attention_count`, `benefit_alerts`. `year` defaults to the current year; invoices are bucketed by their own date in Vienna time |
| GET | `/api/v1/stats/monthly` | Monthly aggregations, filtered by `year` and `member_key` |
| GET | `/api/v1/stats/yearly` | Per-year totals |
| GET | `/api/v1/stats/members` | Per-member breakdown with category split |

### Async boundary

The API is fully async (FastAPI + asyncpg). Celery workers are synchronous; they bridge into async code via `asyncio.get_event_loop().run_until_complete()` in `workers/tasks.py`. Do not introduce `await` directly inside Celery task bodies — use the `_run()` helper or extract an `async def` and call `_run()` on it.

### Auth and multi-tenancy

Every `/api/v1` route (except the webhook, which has its own `X-Webhook-Secret`) goes through `get_current_user` in `api/dependencies.py`, which requires `Authorization: Bearer <API_TOKEN>` (constant-time compare). It fails closed: an empty or `CHANGE_ME` token rejects everything. `user_id` stays a query param that only selects the tenant row; the token is the credential. The frontend asks for the token on its login screen, keeps it in `localStorage`, and returns to login on any 401. CORS allows only `CORS_ORIGINS` (default: `kaiserclaim.home`, `kaiserclaim.didiladi.com`, `localhost:5173`). `tests/test_auth.py` asserts every API route is protected, so a new endpoint cannot forget the dependency. Scripts and the desktop ÖGK worker need `API_TOKEN` in their environment. Replace with per-user JWTs before going multi-user.

Every table has a `user_id` column. All queries in API endpoints must filter by `current_user.id`.

### Backups

The live database is `kaiserclaim` on the shared Postgres in namespace `family` (`postgres-postgresql`), not a Postgres in this repo's manifests; the repo's placeholder `secret.yaml` does not reflect that. `k8s/base/backup.yaml` adds a nightly CronJob (03:15, 30 copies) that writes to the NAS (`/volume1/K3S_Backups/kaiserclaim/`): `db/db-<ts>.sql.gz` (pg_dump) and `storage/storage-<ts>.tar.gz` (invoice files and Merkur documents; browser session dirs excluded because they hold auth cookies). The shared Postgres also has its own nightly `pg_dumpall` (`home-lab/apps/postgres`). Apply with `kubectl apply -k k8s/overlays/homelab/`.

Restore (check the dump first, restore into an empty DB):

```bash
gunzip -c db-<ts>.sql.gz | psql "<postgresql URL of an empty database>"
tar -xzf storage-<ts>.tar.gz -C <storage root>
```

### Merkur result reconciliation

`sync_merkur_inbox` (daily 07:00) stores each Postfach result once (`geschaeftsfall_nr` is unique) and links it to exactly one invoice by patient + date + amount (`_process_scraped_doc`). Candidates are invoices in `MERKUR_SUBMITTED`, `MERKUR_SUBMITTING` or `FAILED`: a result arriving is the proof Merkur received a claim whose submit step crashed or missed the success signal, so it rescues those invoices to `MERKUR_REIMBURSED`/`MERKUR_REJECTED`. Stored documents that are still `UNKNOWN` or unlinked are re-evaluated every sync. New results that match no invoice, or several, are not dropped silently: they trigger a notification for manual review.

### Notifications

`services/notifier.py` posts to Home Assistant's `notify.<HA_NOTIFY_SERVICE>` (Signal). It is a no-op until `HA_URL`, `HA_TOKEN` and `HA_NOTIFY_SERVICE` are real values, and never raises. Every Celery task uses `NotifyOnFailure` (`workers/tasks.py`), which pushes once a task fails for good (retries do not count). `scan_unused_benefits` pushes a digest on Mondays, or daily once a benefit is within 7 days of expiring. Keep messages free of PII.

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

## meine ÖGK calibration status

Target portal is meine ÖGK (`meine.oegk.at`, ID Austria login, always manual), not the old Kundenportal that `OegkBot` still points at. Calibrate with `python scripts/calibrate_oegk.py [--phase lookup|review]`; captures land in `scripts/.oegk_capture/` (gitignored, PII: IBAN, birth date, SV numbers).

**Calibrated (2026-10-24):**
- Submit form up to the last step: date page (`#datumKostenerstattung`, `…btnContinue`), type tabs, upload (`*fileUpload_input` + "Hinzufügen"), für-wen tabs, prefilled bank data, email/phone selects, "Weiter" (`*:weiter`). JSF ids contain `j_idt` parts: match by id suffix or label, never the full id.
- "Eingereichte Rechnungen abfragen": `#vonDat` / `#bisDat` + OK, rows in `#cb_list_done` (`.cb_date`, `.cb_title`, `.cb_status`, `.cb_details`, `.cb_download`), PDF icon triggers a real download. The details page shows patient, SV number, Rechnungsbetrag, doctor and refund.
- Refund PDF parsing: `services/oegk_result_parser.py` (`OegkDocument` rows, identity = `dedupe_key`, there is no case number).

**KNOWN GAP, deliberately not calibrated (decided 2026-10-24):** the `--phase review` run was skipped, so these are unknown:
- The input for the insured person under "für Mitversicherte" (the user types the SV number; selector, format handling and the portal's reaction to a wrong number are unseen).
- The review page after the last "Weiter", the label of the final send button, and the success / reference-number signal after sending.

Consequences:
- Submission to meine ÖGK cannot be built or verified. The selectors in `OegkBot.submit_invoice` are still the old guesses for the Kundenportal and must not be trusted. `submit_to_oegk` stays unusable until the gap is closed.
- Lookup and PDF download (`OegkBot.download_refunds`, `sync_oegk_refunds`, matching) are not affected, but the bot has so far only run against a synthetic fixture. First live check: `python scripts/oegk_download_refunds.py`.
- Interim path: submit by hand in meine ÖGK, let KaiserClaim download and match the refund PDFs, then forward photo + PDF to Merkur. Submission stays disabled via `OEGK_SUBMIT_ENABLED` (default false).
- To close the gap: run `python scripts/calibrate_oegk.py --phase review` (stop before any send button), then implement and fixture-test the submit steps.

## Merkur QR-Code-Einreichung (investigated 2026-10-24, not adopted)

Merkur's wizard has a separate "QR-Code-Einreichung" route (`scripts/calibrate_merkur_qr.py`). What the capture showed:
- Four steps: QR-Code-Scan, Personenzuweisung, Überweisungskonto, Abschluss. **No file input at all**: neither the receipt photo nor any other file can be attached on this route.
- The scan is a live **webcam** widget (`zxing-scanner` with a `<video>`), prompt: "Halten Sie den QR-Code, welcher auf Ihrem **Zusatzbeleg** abgebildet ist, vor die Kamera." There is also a help link ("Haben Sie Probleme beim Scannen des Apotheken-QR-Code?", not opened yet).
- A first manual try with a laptop webcam failed to scan the receipt.
- The prompt names the code on a *Zusatzbeleg*. The Austrian private insurers and the Apothekerkammer introduced a QR code appended to the pharmacy receipt for exactly this (VVO press text, 2023). It is probably **not** the RKSV cash-register QR that `services/rksv_parser.py` decodes; the payload format is unknown.

Decision: pharmacy receipts keep using the calibrated generic upload (`MerkurBot._submit`, photo upload). Building the QR route would need a fake-camera feed (`--use-file-for-fake-video-capture`) and the unknown payload format, for no attachment support. Open questions for the Merkur Berater: what exactly is the Zusatzbeleg code, does the pharmacy print it on request, and is a generic photo upload processed more slowly than a QR submission?

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
