"""
Offline selector regression tests for MerkurBot.

Each test loads a sanitized HTML snapshot captured by scripts/calibrate_merkur.py
and asserts that the bot's selectors resolve to exactly one (or at least one) element.
This catches selector regressions without hitting the live Merkur portal.

To populate the fixtures:
    1. python scripts/calibrate_merkur.py --receipt /path/to/receipt.pdf
    2. Strip PII from scripts/.merkur_capture/*.html (name, policy number, addresses)
    3. Copy sanitized files to tests/fixtures/merkur/

Tests skip automatically when a fixture file is absent.

Fixture → calibration snapshot mapping:
    01_login.html           → captured manually if session expires during calibration
    02_portal_dashboard.html → scripts/.merkur_capture/02_portal_dashboard.html
    03_step1_person.html    → scripts/.merkur_capture/03_step1_person.html
    04_step2_iban.html      → scripts/.merkur_capture/04_step2_iban.html
    05_step3_upload.html    → scripts/.merkur_capture/05_step3_upload.html
    06_step4_summary.html   → scripts/.merkur_capture/06_step4_summary.html
"""
import pytest
from pathlib import Path
from playwright.async_api import async_playwright

FIXTURES = Path(__file__).parent / "fixtures" / "merkur"

# ---------------------------------------------------------------------------
# Confirmed selectors — keep in sync with workers/playwright_bot.py
# ---------------------------------------------------------------------------

# Liferay login portlet (session expired). Confirmed by calibration.
LOGIN_SELECTORS: dict[str, str] = {
    "username": "#username",
    "password": "#password",
    "login_button": "#btlogin",
}

# Liferay portal dashboard — "Einreichung starten" opens Angular SPA in new tab.
PORTAL_SELECTORS: dict[str, str] = {
    "einreichung_starten": 'a[href="/kporclient/einreichung"]',
}

# Angular SPA — Step 1: Versicherte Person (mat-radio-group-1). Confirmed by calibration.
STEP1_SELECTORS: dict[str, str] = {
    "person_radio": 'mat-radio-button[name="mat-radio-group-1"]',
    "weiter_button": "button.mat-stepper-next",
}

# Angular SPA — Step 2: Überweisungskonto (mat-radio-group-2). Confirmed by calibration.
STEP2_SELECTORS: dict[str, str] = {
    "iban_radio": 'input[name="mat-radio-group-2"]',
    "weiter_button": "button.mat-stepper-next",
}

# Angular SPA — Step 3: File upload. TODO: update file_trigger after calibration.
STEP3_SELECTORS: dict[str, str] = {
    "file_input": "input[type=file]",
    "weiter_button": "button.mat-stepper-next",
}

# Angular SPA — Step 4: Zusammenfassung. TODO: update confirm_checkbox + submit after calibration.
STEP4_SELECTORS: dict[str, str] = {
    "confirm_checkbox": "mat-checkbox input[type=checkbox]",
    "submit_button": "button[type=submit]",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_fixture(name: str) -> str:
    path = FIXTURES / f"{name}.html"
    if not path.exists():
        pytest.skip(
            f"Fixture '{name}.html' not yet captured. "
            "Run: python scripts/calibrate_merkur.py, strip PII, "
            "copy to tests/fixtures/merkur/"
        )
    return path.read_text(encoding="utf-8")


async def _assert_selectors(
    html: str,
    selectors: dict[str, str],
    *,
    min_count: int = 1,
) -> None:
    """Assert each selector matches at least min_count elements in the given HTML."""
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.set_content(html, wait_until="domcontentloaded")
        for field, selector in selectors.items():
            count = await page.locator(selector).count()
            assert count >= min_count, (
                f"Selector '{selector}' (field: {field}) matched {count} element(s), "
                f"expected >= {min_count}. Update the selector in workers/playwright_bot.py."
            )
        await browser.close()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

async def test_login_selectors():
    """Login portlet selectors — used when session has expired."""
    html = _load_fixture("01_login")
    await _assert_selectors(html, LOGIN_SELECTORS)


async def test_portal_dashboard_selectors():
    """Liferay portal page — 'Einreichung starten' link that opens Angular SPA."""
    html = _load_fixture("02_portal_dashboard")
    await _assert_selectors(html, PORTAL_SELECTORS)


async def test_step1_person_selectors():
    """Angular SPA step 1 — Versicherte Person radio group and WEITER button."""
    html = _load_fixture("03_step1_person")
    await _assert_selectors(html, STEP1_SELECTORS)


async def test_step2_iban_selectors():
    """Angular SPA step 2 — Überweisungskonto radio group and WEITER button."""
    html = _load_fixture("04_step2_iban")
    await _assert_selectors(html, STEP2_SELECTORS)


async def test_step3_upload_selectors():
    """Angular SPA step 3 — file input and WEITER button."""
    html = _load_fixture("05_step3_upload")
    await _assert_selectors(html, STEP3_SELECTORS)


async def test_step4_summary_selectors():
    """Angular SPA step 4 — confirmation checkbox and submit button."""
    html = _load_fixture("06_step4_summary")
    await _assert_selectors(html, STEP4_SELECTORS)
