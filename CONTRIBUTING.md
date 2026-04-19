# Contributing to KaiserClaim

Thanks for your interest. KaiserClaim is an early-stage project and contributions — bug reports, portal selector fixes, new insurer support, or documentation improvements — are very welcome.

## Before you start

- Check the [open issues](../../issues) to avoid duplicate work.
- For significant new features, open an issue first to discuss the approach.
- The Austrian insurance portal landscape is the main moving target here — fixes to Playwright selectors (`workers/playwright_bot.py`) are especially valuable.

## Development setup

```bash
git clone https://github.com/YOUR_ORG/kaiserclaim.git
cd kaiserclaim

cp .env.example .env
# Fill in credentials for your own Merkur/ÖGK account — tests that hit the live portals require this

docker compose up --build
```

The API runs at `http://localhost:8000/docs`.

## Making changes

**Database model changes** always require a migration:

```bash
# After editing models/domain.py
alembic revision --autogenerate -m "short description"
# Review the generated file in alembic/versions/ before committing
alembic upgrade head
```

**New insurers** — the cleanest place to add a new private insurer is a new bot class in `workers/playwright_bot.py` and a corresponding Celery task in `workers/tasks.py`. Extend `InvoiceStatus` in `models/domain.py` and add a new migration.

**New benefit rule types** — extend the `LimitType` enum in `models/domain.py` and update the Gemini prompt in `services/llm_auditor.py`.

## Pull requests

- Keep PRs focused. A PR that fixes Merkur selectors should not also refactor the OCR engine.
- Include a short description of what was tested manually (live portal, local Docker stack, or unit test).
- If you're mapping new portal selectors, note which portal version / date you tested against — these drift over time.

## Portal credentials and privacy

**Do not commit real credentials, cookies, or browser session data.** The `.oegk_browser_session/` directory is in `.gitignore` for this reason. Anonymised receipt fixtures for testing are welcome; real patient data is not.

## Reporting portal breakage

Austrian insurance portals change their HTML without notice. If a bot stops working, open an issue with:
- Which portal (Merkur / ÖGK)
- Which step failed (login, file upload, submission, download)
- The error or symptom (no need to share screenshots with personal data)

## License

By contributing you agree that your contributions will be licensed under the [MIT License](LICENSE).
