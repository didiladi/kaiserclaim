# KaiserClaim: Project Analysis and Task List

Analysis date: 2026-07-03. Scope: full repo review (architecture, workflows, security, ops) with the goal of making the app usable for single-user daily operation on the homelab (k3s / docker compose).

**TL;DR:** The Merkur pharmacy short-track (upload, OCR, submit, inbox sync) is largely built and is the strongest part of the codebase. Before first real use, the biggest risks are: a genuine double-submission bug in the Merkur flow, invoices that strand forever on failure, no application-level auth, and two path-injection endpoints. The entire ÖGK arm is dead code. Observability is print-only, and there are no backups of health/financial data.

---

## Part 1: Findings

### Critical (fix before first real submission)

1. **Double-submission risk to Merkur.**
   `submit_to_merkur` (`workers/tasks.py:141-169`) sets `MERKUR_SUBMITTED` only *after* the portal submit succeeds. Success detection is a substring check on body text ("erfolgreich" / "eingereicht", `workers/playwright_bot.py:316`). If the portal accepts the claim but the heuristic returns false, or the worker dies between submit-click and `_set_status`, Celery retries (3x, 120s) and **submits the same claim to Merkur again**. No submission-attempt ledger, no Geschaeftsfall-Nr captured at submit time, no dedup.

2. **No application-level authentication.**
   `api/dependencies.py:11-22` trusts a plain `user_id` query param; anyone who knows the UUID has full read/write access. `frontend/src/api.ts:1` hardcodes `USER_ID = "00000000-...-0001"`; `frontend/src/pages/Login.tsx:23` is a setTimeout fake that only checks the email contains "@". CORS is wildcard on everything (`main.py:19-24`). The only real protection is the Traefik forwardAuth on the *external* ingress (`k8s/base/middleware-auth.yaml`); the internal `kaiserclaim.home` route and docker compose (`0.0.0.0:8000`) are wide open.

3. **Arbitrary path read/write via the API.**
   - `POST /api/v1/invoices/` (`api/endpoints/invoices.py:75-89`) accepts a client-supplied `file_path` (`schemas/payload.py:147`) that `run_ocr` reads verbatim (`workers/tasks.py:110-119`): an arbitrary-file-read primitive. It also duplicates `/upload`.
   - `POST /api/v1/webhooks/oegk-refund-ready` (`api/endpoints/webhooks.py:11-26`) has **no auth dependency at all** and forwards a client-supplied `output_dir` into `poll_oegk_refund`, which writes files there.

4. **Invoices strand forever on failure; OCR nulls advance silently.**
   `InvoiceStatus` has no `FAILED` / `NEEDS_REVIEW` state. `run_ocr`, `submit_to_merkur`, `submit_to_oegk` all end in `raise self.retry(...)` (`tasks.py:137-138, 168-169, 194-195`); after retries exhaust, the row sits in `OCR_PROCESSING` or `READY_FOR_MERKUR` with no user-visible signal. Worse: when OCR/regex finds nothing, the invoice still advances to `READY_FOR_MERKUR` with `amount=None, date=None` (`tasks.py:124-132`), which would then be submitted as `amount=0.0` (`tasks.py:156`).

5. **Live credentials in plaintext on disk.**
   `.env` contains the real Merkur portal password and Gemini API key. It is gitignored and confirmed absent from git history, so no leak via the repo, but it sits unencrypted on the workstation (contrary to the sops-everywhere pattern in home-lab). `SECRET_KEY` is still `change-me-in-production` (`core/config.py:29`), currently unused but a latent trap once auth is added.

### Major (half the product missing, or silently wrong data)

6. **The entire ÖGK arm is orphaned dead code.**
   - `submit_to_oegk` (`tasks.py:172-195`) is never dispatched anywhere (no `.delay()` call).
   - `run_ocr` hardcodes `READY_FOR_MERKUR` for *every* invoice regardless of category (`tasks.py:131`), so nothing can enter the ÖGK path.
   - `OegkBot._submit` selectors are uncalibrated guesses (`workers/playwright_bot.py:608-631`, e.g. `input[name=amount]`); no ÖGK calibration script exists (unlike Merkur).
   - Statuses `READY_FOR_OEGK`, `OEGK_SUBMITTED`, `OEGK_REFUNDED`, `COMPLETED` are unreachable; `_finalize_invoice` (`tasks.py:72-91`) has no callers.
   - `OegkBot` needs a headed browser for ID-Austria 2FA (`headless=False`, 180s wait, `playwright_bot.py:613-615`); compose sets `DISPLAY: ""`, so it cannot run in the current deployment anyway.

7. **Dashboard numbers are estimates presented as facts.**
   `_REIMBURSEMENT_RATE = 0.82` (`api/endpoints/stats.py:21`) is applied to invoice amounts even though the real value exists in `MerkurDocument.reimbursed_amount`. All three stats endpoints default to `year=2026` hardcoded (`stats.py:40, 185, 263`): dashboards silently go empty in January 2027. Stats also aggregate on `created_at`, not the invoice date.

8. **Merkur sync ignores per-user credentials.**
   `sync_merkur_inbox` (`tasks.py:199-244`) loops over all users but logs in with the single global `MERKUR_USERNAME`/`MERKUR_PASSWORD`. Harmless while single-user, broken the moment a second user exists.

9. **Unused-benefit alerting is a no-op.**
   `scan_unused_benefits` (`tasks.py:354-435`) computes under-used benefits nearing reset daily at 08:00, then only `print()`s them. Nothing is persisted, nothing is pushed. The feature effectively does not exist for the user.

### Moderate (robustness and operations)

10. **Observability is `print()` only, including PII.**
    No `logging` module anywhere; ~20 `print(..., flush=True)` calls. `tasks.py:111-122` prints raw decoded QR content, dates, and amounts (health/financial data) to pod logs. No Flower, no Sentry, no failure notifications; if the daily beat jobs fail, the only signal is pod logs nobody reads.

11. **CI covers 2 of 6 test files.**
    `.github/workflows/tests.yml` runs only `test_regex_parser.py` and `test_rksv_parser.py`. The Merkur selector fixture tests (the safety net the calibration workflow depends on) and all DB/API tests are not gated. `MerkurBot._submit` logic and the task state machine have no unit tests at all. No coverage tooling.

12. **Fragile portal automation, weak confirmation.**
    Selectors lean on Angular Material internals (`mat-mdc-radio-touch-target`, `#mat-mdc-checkbox-0-input`, JS `element.click()` to bypass disabled guards). Inbox selectors are self-described as "provisional" (`playwright_bot.py:329-330`). No screenshot/HTML artifact is saved on submission, so a disputed submission leaves no evidence.

13. **No backups of health data.**
    Invoice scans and the DB live on a node-local `local-path` RWO PVC (`k8s/base/pvc.yaml`). No dump/backup job exists. The home-lab repo already has the Vaultwarden-to-NAS backup CronJob pattern (nightly 03:00, 30-day retention) that fits exactly.

14. **Assorted smaller issues.**
    - `PATCH /invoices/{id}/status` (`invoices.py:141-153`) allows any transition, bypassing the state machine.
    - No upload size limit (`invoices.py:57-58`, raw `copyfileobj`).
    - `MERKUR_SUBMITTED` with `UNKNOWN` inbox result stays stranded forever; ambiguous matches are silently dropped (`tasks.py:320`).
    - `_run` uses deprecated `asyncio.get_event_loop().run_until_complete()` (`tasks.py:55`); fragile on Python 3.12.
    - N+1 aggregate queries in `contracts.py:224-229`, `stats.py:71-78, 149-154` (while `contracts.py:388-394` does batch correctly).
    - Dead code: `services/merkur_result_parser.py` (only tests import it), legacy `parse_contract` (`llm_auditor.py:161-179`), dead imports (`contracts.py:36-37`). `InvoiceRead.model_validate` swallows all exceptions (`schemas/payload.py:220-221`); ~30 broad `except Exception` overall.
    - `BenefitRuleCreate` (`schemas/payload.py:76-81`) only exposes legacy fields; `POST /contracts/{id}/benefits` cannot set `benefit_kind`, `reset_period`, `category`, `reimbursement_pct`.
    - Deps: `Pillow`, `numpy`, `pyzbar`, `zxing-cpp` unpinned; `google-generativeai` 0.8.3 is the deprecated SDK generation. Docker image python 3.11 vs CI python 3.12. Deprecated `bases:` key in `k8s/overlays/homelab/kustomization.yaml`. Compose publishes Postgres 5432 with password `secret`.
    - Docs drift: README claims migrations 0001-0003 and a 6-model schema (actual: 0006, 9 tables); CLAUDE.md state diagram omits `MERKUR_REIMBURSED`/`MERKUR_REJECTED`; docs say Gemini 1.5 Flash, code pins `gemini-2.5-flash` (`llm_auditor.py:23`).

### What is in good shape

- RKSV QR parsing with OCR/regex fallback: well built and unit tested.
- Gemini contract parsing (two-stage persons/tariffs then benefits) works end-to-end with sane 503 handling.
- Merkur inbox sync dedups correctly on `geschaeftsfall_nr` (unique constraint); `BenefitUsage` writes are idempotent.
- Migrations: clean linear chain 0001-0006, enum evolution handled correctly.
- Docker/k8s setup is solid: multi-stage build, Playwright install handled, healthchecks, probes, resource limits, migrate job, secrets via `envFrom` with a properly excluded placeholder `secret.yaml`.
- Full mobile-first React PWA exists and is served by the API.
- Git hygiene: clean tree, no secrets in history, PII capture dirs gitignored.

---

## Part 2: Task list to make it usable

### P0: Safety before the first real submission

- [x] **Make Merkur submission idempotent (partial: CAS claim + no retry past click; no ledger or confirmation capture yet).** Create a submission-attempt record *before* clicking submit; on retry, check the ledger and/or the Merkur inbox for an existing Geschaeftsfall before re-submitting; capture the confirmation number or a screenshot at submit time. Never blind-retry past the submit click. (`workers/tasks.py:141-169`, `workers/playwright_bot.py:174-316`)
- [x] **Add `FAILED` and `NEEDS_REVIEW` invoice statuses (done, incl. `PATCH /invoices/{id}` recovery for NEEDS_REVIEW; no review UI yet).** On retry exhaustion, set `FAILED` (use Celery `on_failure` or a final except branch). When OCR yields `amount=None` or `date=None`, set `NEEDS_REVIEW` instead of `READY_FOR_MERKUR`, and surface both states in the UI. Requires a migration (`ALTER TYPE ... ADD VALUE`, same pattern as 0004). (`models/domain.py:38-48`, `tasks.py:124-138`)
- [x] **Remove the `file_path` create endpoint or restrict it to `STORAGE_ROOT`.** `/upload` covers the real use case. (`api/endpoints/invoices.py:75-89`)
- [x] **Fix the webhook:** add the auth dependency and stop accepting `output_dir` from the client (derive it server-side). Or delete it until the ÖGK arm exists. (`api/endpoints/webhooks.py`)
- [ ] **Rotate the Merkur password and Gemini key** (they sat in plaintext; treat as exposed), set a real `SECRET_KEY`, and move `.env` handling toward the sops/age pattern used in home-lab.
- [ ] **Calibrate before going live:** run `scripts/calibrate_merkur.py` and `calibrate_merkur_inbox.py` against the live portal, update the `_INBOX_*` constants and submit selectors, commit sanitized fixtures, then do at least one full `MERKUR_DRY_RUN=true` cycle and one `stop_before_submit` run.

### P1: Make daily use trustworthy

- [x] **Minimal real auth (done 2026-10-04):** a static bearer token checked in `get_current_user` is enough for single-user; store it in the k8s secret, have the frontend send it, delete the fake login or wire it to the token. Restrict CORS to the actual origins (`kaiserclaim.home`, `kaiserclaim.didiladi.com`, `localhost:5173`). (`api/dependencies.py`, `main.py:19-24`, `frontend/src/api.ts`, `frontend/src/pages/Login.tsx`)
- [x] **Failure notifications (done; stays off until `HA_URL`/`HA_TOKEN`/`HA_NOTIFY_SERVICE` are set, the Signal service name is not in the HA repo).** On task failure and on beat-job errors, notify via the existing HA Signal notify service (same pattern as other homelab automations). A small helper called from Celery `on_failure` covers all tasks at once.
- [x] **Wire `scan_unused_benefits` to notifications** (Signal message listing expiring benefits) instead of `print()`. (`tasks.py:354-435`)
- [x] **Real dashboard numbers (done; also fixed: invoices finalize to MERKUR_REIMBURSED, never COMPLETED, so reimbursed was always ~0):** use `MerkurDocument.reimbursed_amount` where available, label the 82% figure as an estimate where not; default `year` to the current year; aggregate on invoice `date` with `created_at` fallback. (`api/endpoints/stats.py:21, 40, 185, 263`)
- [ ] **Backups:** nightly pg_dump + storage rsync to the NAS, reusing the home-lab Vaultwarden CronJob pattern (03:00, 30-day retention). This is health data; it must survive node loss.
- [ ] **Replace `print()` with the `logging` module** and stop logging QR contents/amounts at info level. (`workers/tasks.py`, `workers/playwright_bot.py`)
- [ ] **Handle stuck `MERKUR_SUBMITTED`:** re-evaluate `UNKNOWN` results on subsequent syncs, and flag ambiguous invoice matches for manual review instead of silently dropping them. (`tasks.py:315-325`)

### P2: Decide and complete the ÖGK arm

- [x] **Decision: ÖGK submission is wanted (2026-10-04).**
- [ ] If yes:
  - [x] Route by category in `run_ocr` (pharmacy vs standard, the `_derive_pipeline` logic already exists in `schemas/payload.py:164`) and dispatch `submit_to_oegk`. (`tasks.py:131`)
  - [ ] `scripts/calibrate_oegk.py` is written (harness only). Still to do after running it live: replace the placeholder selectors and success check, add fixture tests. (`playwright_bot.py:608-663`)
  - [x] Headed-browser 2FA: solved with a desktop worker on the dedicated `oegk` queue (`scripts/run_oegk_worker.sh`). Alternatives considered: run the ÖGK bot on the desktop, or a VNC/Xvfb sidecar in the pod; the persistent-session volume design already exists.
  - [x] (code done; matching refund PDFs to invoices needs a key from calibration) Wire the refund path: `poll_oegk_refund`, transition to `READY_FOR_MERKUR`, and call `_finalize_invoice` so `COMPLETED` and `BenefitUsage` actually happen. (`tasks.py:72-91, 438+`)
- [ ] If no: delete `OegkBot`, `submit_to_oegk`, `poll_oegk_refund`, the webhook, and the unreachable statuses; simplify the enum and the UI stepper.

### P3: Hardening and quality

- [ ] Validate transitions in `PATCH /invoices/{id}/status` against the state machine (allow explicit admin override if needed). (`invoices.py:141-153`)
- [ ] Enforce an upload size limit (e.g. 20 MB) in `/upload`. (`invoices.py:53-58`)
- [ ] CI: run the full test suite with a Postgres service container and seeded test user; add the Merkur fixture tests to the gate; add coverage reporting. (`.github/workflows/tests.yml`, `tests/conftest.py`)
- [ ] Replace `asyncio.get_event_loop()` in `_run` with `asyncio.run()` or a per-worker persistent loop; align Docker image (3.11) and CI (3.12) Python versions. (`tasks.py:55`)
- [ ] Batch the N+1 quota queries using the pattern already present in `contracts.py:388-394`. (`contracts.py:224-229`, `stats.py:71-78, 149-154`)
- [ ] Extend `BenefitRuleCreate`/`BenefitRuleRead` to the current model fields (`benefit_kind`, `reset_period`, `category`, `reimbursement_pct`). (`schemas/payload.py:76-81`, `contracts.py:237, 245-258`)
- [ ] Delete dead code: `services/merkur_result_parser.py` (or make it the production parser), legacy `parse_contract`, dead imports in `contracts.py:36-37`, `_finalize_invoice` if the ÖGK arm is dropped. Replace the `InvoiceRead.model_validate` bare-except with explicit handling. (`schemas/payload.py:209-222`)
- [ ] Pin `Pillow`, `numpy`, `pyzbar`, `zxing-cpp`; plan migration from `google-generativeai` to the `google-genai` SDK.
- [ ] Deployment tidy-up: stop publishing Postgres 5432 (or bind to 127.0.0.1), change the DB password, drop the obsolete compose `version:` key, replace `bases:` with `resources:` in the homelab overlay.
- [ ] Sync README/CLAUDE.md with reality (migrations 0006, 9 tables, actual state diagram incl. `MERKUR_REIMBURSED`/`MERKUR_REJECTED`, Gemini 2.5 Flash).

---

## Suggested order of attack

1. P0 items are a prerequisite for the first live Merkur submission; the idempotency fix and the FAILED/NEEDS_REVIEW states are the two that protect you from real-world damage.
2. P1 makes it something you can trust day-to-day without watching pod logs.
3. P2 is a scope decision, not a bug fix; the app is already useful Merkur-only.
4. P3 can be done incrementally alongside normal use.
