"""
Playwright automation bots.

- MerkurBot: fully headless, submits invoice PDF to Merkur portal.
- OegkBot: uses a persistent browser context so the ID-Austria 2FA session
  survives across runs (the user authenticates once; subsequent runs reuse cookies).
"""
import asyncio
from pathlib import Path

from playwright.async_api import async_playwright, BrowserContext, Page

from core.config import get_settings

settings = get_settings()

_OEGK_USER_DATA_DIR = Path(settings.storage_root) / ".oegk_browser_session"
_MERKUR_PORTAL_URL = "https://www.merkur.at/kundenportal"
_OEGK_PORTAL_URL = "https://www.oegk.at/kundenportal"


# ---------------------------------------------------------------------------
# Merkur (fully headless)
# ---------------------------------------------------------------------------

class MerkurBot:
    async def submit_pharmacy_receipt(
        self,
        invoice_pdf: str,
        amount: float,
        date: str,
        stop_before_submit: bool = False,
    ) -> bool:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            context = await browser.new_context(accept_downloads=True)
            page = await context.new_page()
            try:
                success = await self._submit(
                    page, invoice_pdf, amount, date, stop_before_submit
                )
                return success
            finally:
                await browser.close()

    async def _submit(
        self,
        page: Page,
        invoice_pdf: str,
        amount: float,
        date: str,
        stop_before_submit: bool = False,
    ) -> bool:
        await page.goto(_MERKUR_PORTAL_URL, wait_until="networkidle")

        # --- Login ---
        # TODO: replace these selectors with calibrated values from scripts/calibrate_merkur.py
        await page.fill("#username", settings.merkur_username)
        await page.fill("#password", settings.merkur_password)
        await page.click("button[type=submit]")
        await page.wait_for_load_state("networkidle")

        # Verify login succeeded: if we're still on the login page, credentials are wrong.
        url = page.url.lower()
        still_on_login = (
            "login" in url
            or "anmelden" in url
            or await page.locator("#username").count() > 0
        )
        if still_on_login:
            raise RuntimeError(
                "Merkur login failed — check MERKUR_USERNAME / MERKUR_PASSWORD in .env"
            )

        # --- Navigate to refund submission ---
        await page.click("text=Kostenerstattung")
        await page.click("text=Neue Einreichung")
        await page.wait_for_selector("input[type=file]")

        # --- Upload invoice PDF ---
        async with page.expect_file_chooser() as fc_info:
            await page.click("text=Datei hochladen")
        file_chooser = await fc_info.value
        await file_chooser.set_files(invoice_pdf)

        # --- Fill metadata ---
        await page.fill("input[name=amount]", str(amount))
        await page.fill("input[name=date]", date)

        if stop_before_submit:
            return False

        # --- Submit ---
        await page.click("button[type=submit]")
        await page.wait_for_load_state("networkidle")

        # TODO: replace with a specific confirmation element found during calibration
        return "erfolgreich" in (await page.text_content("body") or "").lower()


# ---------------------------------------------------------------------------
# ÖGK (persistent context — user handles 2FA interactively once)
# ---------------------------------------------------------------------------

class OegkBot:
    async def submit_invoice(self, invoice_pdf: str, amount: float, date: str) -> bool:
        _OEGK_USER_DATA_DIR.mkdir(parents=True, exist_ok=True)
        async with async_playwright() as pw:
            context: BrowserContext = await pw.chromium.launch_persistent_context(
                str(_OEGK_USER_DATA_DIR),
                headless=False,  # must be visible so user can complete 2FA when needed
                accept_downloads=True,
            )
            page = context.pages[0] if context.pages else await context.new_page()
            try:
                return await self._submit(page, invoice_pdf, amount, date)
            finally:
                await context.close()

    async def _submit(self, page: Page, invoice_pdf: str, amount: float, date: str) -> bool:
        await page.goto(_OEGK_PORTAL_URL, wait_until="networkidle")

        # If the session has expired the portal will redirect to the ID-Austria
        # login page — the user completes 2FA interactively; we wait up to 3 min.
        if "login" in page.url or "anmelden" in page.url:
            print("[OegkBot] 2FA required — please authenticate in the browser window.")
            await page.wait_for_url(f"{_OEGK_PORTAL_URL}/**", timeout=180_000)

        await page.click("text=Leistungsabrechnung")
        await page.click("text=Neue Einreichung")
        await page.wait_for_selector("input[type=file]")

        async with page.expect_file_chooser() as fc_info:
            await page.click("text=Datei hochladen")
        file_chooser = await fc_info.value
        await file_chooser.set_files(invoice_pdf)

        await page.fill("input[name=amount]", str(amount))
        await page.fill("input[name=date]", date)
        await page.click("button[type=submit]")
        await page.wait_for_load_state("networkidle")

        return "eingereicht" in (await page.text_content("body") or "").lower()

    async def download_refund_pdf(self, output_dir: str) -> str | None:
        """Poll the ÖGK portal for a new refund PDF and download it."""
        _OEGK_USER_DATA_DIR.mkdir(parents=True, exist_ok=True)
        async with async_playwright() as pw:
            context = await pw.chromium.launch_persistent_context(
                str(_OEGK_USER_DATA_DIR),
                headless=False,
                accept_downloads=True,
            )
            page = context.pages[0] if context.pages else await context.new_page()
            try:
                return await self._download_refund(page, output_dir)
            finally:
                await context.close()

    async def _download_refund(self, page: Page, output_dir: str) -> str | None:
        await page.goto(_OEGK_PORTAL_URL, wait_until="networkidle")
        await page.click("text=Meine Abrechnungen")

        # Look for an undownloaded refund document
        refund_links = await page.query_selector_all("a[href*='refund'], a[href*='abrechnung']")
        if not refund_links:
            return None

        async with page.expect_download() as dl_info:
            await refund_links[0].click()
        download = await dl_info.value

        dest = Path(output_dir) / download.suggested_filename
        await download.save_as(str(dest))
        return str(dest)
