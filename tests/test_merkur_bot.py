"""
Offline selector regression tests for MerkurBot.

Each test loads a sanitized HTML snapshot captured by scripts/calibrate_merkur.py
and asserts that the bot's selectors resolve to exactly one element on the page.
This catches selector regressions without hitting the live Merkur portal.

To populate the fixtures:
    1. python scripts/calibrate_merkur.py
    2. Strip PII from scripts/.merkur_capture/*.html (name, policy number, addresses)
    3. Copy sanitized files to tests/fixtures/merkur/

Tests skip automatically when a fixture file is absent.
"""
import pytest
from pathlib import Path
from playwright.async_api import async_playwright

FIXTURES = Path(__file__).parent / "fixtures" / "merkur"

# Selectors used by MerkurBot._submit — keep in sync with workers/playwright_bot.py.
# Update these after running the calibration harness and confirming real values.
LOGIN_SELECTORS: dict[str, str] = {
    "username": "#username",
    "password": "#password",
    "login_button": "button[type=submit]",
}

DASHBOARD_SELECTORS: dict[str, str] = {
    "reimbursement_nav": "text=Kostenerstattung",
}

SUBMISSION_LIST_SELECTORS: dict[str, str] = {
    "new_submission": "text=Neue Einreichung",
}

FORM_SELECTORS: dict[str, str] = {
    "file_input": "input[type=file]",
    "amount": "input[name=amount]",
    "date": "input[name=date]",
    "submit_button": "button[type=submit]",
}


def _load_fixture(name: str) -> str:
    path = FIXTURES / f"{name}.html"
    if not path.exists():
        pytest.skip(
            f"Fixture '{name}.html' not yet captured. "
            "Run: python scripts/calibrate_merkur.py, strip PII, "
            "copy to tests/fixtures/merkur/"
        )
    return path.read_text(encoding="utf-8")


async def _assert_selectors(html: str, selectors: dict[str, str]) -> None:
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.set_content(html, wait_until="domcontentloaded")
        for field, selector in selectors.items():
            count = await page.locator(selector).count()
            assert count == 1, (
                f"Selector '{selector}' (field: {field}) matched {count} element(s), "
                f"expected exactly 1. Update the selector in workers/playwright_bot.py."
            )
        await browser.close()


async def test_login_form_selectors():
    html = _load_fixture("01_login")
    await _assert_selectors(html, LOGIN_SELECTORS)


async def test_dashboard_selectors():
    html = _load_fixture("02_dashboard")
    await _assert_selectors(html, DASHBOARD_SELECTORS)


async def test_submission_list_selectors():
    html = _load_fixture("03_kostenerstattung")
    await _assert_selectors(html, SUBMISSION_LIST_SELECTORS)


async def test_submission_form_selectors():
    html = _load_fixture("04_submission_form")
    await _assert_selectors(html, FORM_SELECTORS)
