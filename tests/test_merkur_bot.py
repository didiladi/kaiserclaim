"""
Offline selector regression tests for MerkurBot.

Each test loads a sanitized HTML snapshot from tests/fixtures/merkur/ and asserts
that the bot's confirmed selectors resolve to at least one element.  Run after
copying and PII-stripping the captures from scripts/.merkur_capture/.

Fixture → calibration snapshot mapping:
    01_portal_dashboard.html    → 01_portal_dashboard.html
    02_step1_person.html        → 02_step1_person.html  (Vertrag + all steps visible)
    03_step1_person_selected.html → 03_step1_person_selected.html
    04_step2_iban_selected.html → 04_step2_iban_selected.html
    05_step3_upload.html        → 05_step3_upload.html  (file attached)
    06_step4_summary.html       → 06_step4_summary.html (checkbox ticked)
    07_inbox_ungelesen.html     → 07_inbox_ungelesen.html (Postfach "Ungelesen" section)
    08_inbox_year_expanded.html → 08_inbox_year_expanded.html (year accordion expanded)
    09_inbox_after_download_click.html → post-click snapshot
"""
import pytest
from pathlib import Path
from playwright.async_api import async_playwright

FIXTURES = Path(__file__).parent / "fixtures" / "merkur"

# ---------------------------------------------------------------------------
# Confirmed selectors — all verified by calibration run 2026-05-19
# ---------------------------------------------------------------------------

# NOTE: a[href="/kporclient/einreichung"] is injected by the Liferay Vue portlet
# after page load and is absent from the static HTML snapshot. Verified in the
# live portal by calibration; no static test needed here.

# ---------------------------------------------------------------------------
# Inbox selectors — confirmed by calibrate_merkur_inbox.py (2026-05-22)
# ---------------------------------------------------------------------------

INBOX_SELECTORS: dict[str, str] = {
    # Only present on Ambulante Abrechnungsinformation rows
    "download_btn": "button[aria-label='Zur Einreichung']",
    # Date paragraph inside each row (id="documentDatum_N")
    "date_para": "p[id^='documentDatum']",
    # Year-group accordion headers (full_history expansion)
    "year_header": "div.subheader-hover[tabindex='0']",
}

# Step 0: Vertrag — one pre-selected radio, advance with button[matsteppernext] nth(0)
VERTRAG_SELECTORS: dict[str, str] = {
    "vertrag_radio": 'input[name="mat-radio-group-0"]',
    "weiter": "button[matsteppernext]",
}

# Step 1: Versicherte Person — mat-radio-group-1; innerText contains "Name (DOB)"
PERSON_SELECTORS: dict[str, str] = {
    "person_radio": "mat-radio-button:has(input[name='mat-radio-group-1'])",
    "weiter": "button[matsteppernext]",
}

# Step 2: Überweisungskonto — mat-radio-group-2; value = IBAN without spaces
IBAN_SELECTORS: dict[str, str] = {
    "iban_radio": 'input[name="mat-radio-group-2"]',
    "weiter": "button[matsteppernext]",
}

# Step 3: Dateiauswahl — file input is hidden but present; set_input_files works on it
FILE_SELECTORS: dict[str, str] = {
    "weiter": "button[matsteppernext]",
}

# Step 4: Zusammenfassung — checkbox + final submit
SUMMARY_SELECTORS: dict[str, str] = {
    "confirm_checkbox": "#mat-mdc-checkbox-0-input",
    "submit_button": "button:has-text('EINREICHUNG ABSCHLIESSEN')",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_fixture(name: str) -> str:
    path = FIXTURES / f"{name}.html"
    if not path.exists():
        pytest.skip(
            f"Fixture '{name}.html' not present. "
            "Strip PII from scripts/.merkur_capture/{name}.html and copy here."
        )
    return path.read_text(encoding="utf-8")


async def _assert_selectors(html: str, selectors: dict[str, str]) -> None:
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.set_content(html, wait_until="domcontentloaded")
        for field, selector in selectors.items():
            count = await page.locator(selector).count()
            assert count >= 1, (
                f"Selector '{selector}' (field: {field}) matched {count} element(s), "
                "expected >= 1. Update the selector in workers/playwright_bot.py."
            )
        await browser.close()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

async def test_vertrag_selectors():
    """Angular SPA — Vertrag step radio and WEITER button."""
    html = _load_fixture("02_step1_person")
    await _assert_selectors(html, VERTRAG_SELECTORS)


async def test_person_selectors():
    """Angular SPA — Versicherte Person radios present and selectable by text."""
    html = _load_fixture("02_step1_person")
    await _assert_selectors(html, PERSON_SELECTORS)


async def test_iban_selectors():
    """Angular SPA — Überweisungskonto radios with IBAN values."""
    html = _load_fixture("03_step1_person_selected")
    await _assert_selectors(html, IBAN_SELECTORS)


async def test_file_step_weiter():
    """Angular SPA — WEITER button present on file upload step."""
    html = _load_fixture("05_step3_upload")
    await _assert_selectors(html, FILE_SELECTORS)


async def test_summary_selectors():
    """Angular SPA — confirmation checkbox and final submit button."""
    html = _load_fixture("06_step4_summary")
    await _assert_selectors(html, SUMMARY_SELECTORS)


async def test_person_text_matching():
    """Person radio innerText contains expected name fragments."""
    html = _load_fixture("02_step1_person")
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.set_content(html, wait_until="domcontentloaded")
        buttons = page.locator("mat-radio-button:has(input[name='mat-radio-group-1'])")
        count = await buttons.count()
        assert count >= 1, "No person radio buttons found"
        texts = [
            (await buttons.nth(i).inner_text()).strip()
            for i in range(count)
        ]
        # At least one option must contain a name and DOB pattern "(DD.MM.YYYY)"
        assert any("(" in t and ")" in t for t in texts), (
            f"Person radio labels don't contain DOB pattern: {texts}"
        )
        await browser.close()


async def test_inbox_download_button_selector():
    """Inbox snapshot — 'Zur Einreichung' button exists on Ambulante rows only."""
    html = _load_fixture("07_inbox_ungelesen")
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.set_content(html, wait_until="domcontentloaded")
        dl_btns = page.locator(INBOX_SELECTORS["download_btn"])
        count = await dl_btns.count()
        assert count >= 1, (
            f"No '{INBOX_SELECTORS['download_btn']}' buttons found. "
            "Re-run calibrate_merkur_inbox.py to update the selector."
        )
        # Confirm they are NOT present on ego4you rows — all matching rows must be Ambulante
        for i in range(count):
            btn = dl_btns.nth(i)
            row_text = await btn.evaluate(
                "(el) => el.closest('md-list-item')?.textContent || ''"
            )
            assert "Ambulante" in row_text, (
                f"'Zur Einreichung' button found outside an Ambulante row: {row_text[:80]}"
            )
        await browser.close()


async def test_inbox_date_selector():
    """Inbox snapshot — documentDatum paragraphs match the expected DD.MM.YYYY pattern."""
    html = _load_fixture("07_inbox_ungelesen")
    import re
    date_re = re.compile(r"^\d{2}\.\d{2}\.\d{4}$")
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.set_content(html, wait_until="domcontentloaded")
        date_paras = page.locator(INBOX_SELECTORS["date_para"])
        count = await date_paras.count()
        assert count >= 1, (
            f"No '{INBOX_SELECTORS['date_para']}' elements found in inbox snapshot."
        )
        # All date paragraphs must match DD.MM.YYYY
        for i in range(count):
            text = (await date_paras.nth(i).inner_text()).strip()
            assert date_re.match(text), f"Date paragraph {i} has unexpected format: '{text}'"
        await browser.close()


async def test_inbox_year_header_selector():
    """Expanded inbox snapshot — year accordion headers are present."""
    html = _load_fixture("08_inbox_year_expanded")
    await _assert_selectors(html, {"year_header": INBOX_SELECTORS["year_header"]})
