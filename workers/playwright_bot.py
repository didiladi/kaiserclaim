"""
Playwright automation bots.

- MerkurBot: uses a persistent browser context so the OAuth session survives
  across runs. The portal is at https://portal.merkur.at/ (OAuth2/Liferay).
  Run scripts/calibrate_merkur.py once to seed the session and discover selectors.
- OegkBot: uses a persistent browser context so the ID-Austria 2FA session
  survives across runs (the user authenticates once; subsequent runs reuse cookies).
"""
import asyncio
from pathlib import Path

from playwright.async_api import async_playwright, BrowserContext, Page

from core.config import get_settings

settings = get_settings()

_MERKUR_USER_DATA_DIR = Path(settings.storage_root) / ".merkur_browser_session"
_OEGK_USER_DATA_DIR = Path(settings.storage_root) / ".oegk_browser_session"
_MERKUR_PORTAL_URL = "https://portal.merkur.at/"
_MERKUR_FORM_URL = "https://portal.merkur.at/de/leistungseinreichung"
_OEGK_PORTAL_URL = "https://www.oegk.at/kundenportal"


# ---------------------------------------------------------------------------
# Merkur (persistent session — OAuth login survives across runs)
# ---------------------------------------------------------------------------

class MerkurBot:
    async def submit_pharmacy_receipt(
        self,
        invoice_pdf: str,
        amount: float,
        date: str,
        patient_name: str = "",
        stop_before_submit: bool = False,
    ) -> bool:
        _MERKUR_USER_DATA_DIR.mkdir(parents=True, exist_ok=True)
        async with async_playwright() as pw:
            context: BrowserContext = await pw.chromium.launch_persistent_context(
                str(_MERKUR_USER_DATA_DIR),
                headless=True,
                accept_downloads=True,
            )
            page = context.pages[0] if context.pages else await context.new_page()
            try:
                return await self._submit(
                    context, page, invoice_pdf, amount, date, patient_name, stop_before_submit
                )
            finally:
                await context.close()

    async def _dismiss_cookie_banner(self, page: Page) -> None:
        for _sel in ["button[aria-label='Ablehnen']", "button[aria-label='Alles akzeptieren']"]:
            try:
                btn = page.locator(_sel)
                if await btn.count() > 0 and await btn.first.is_visible():
                    await btn.first.click()
                    await page.wait_for_timeout(500)
                    return
            except Exception:
                continue

    async def _ensure_logged_in(self, page: Page, *, fallback_url: str | None = None) -> None:
        """Login via the portal if the session has expired.

        After login the portal redirects via the embedded 'goto' param.
        If it still ends up on an unrelated page, navigate to fallback_url when given.
        """
        if not settings.merkur_username:
            raise RuntimeError("Merkur login failed: MERKUR_USERNAME is not set")
        _needs_login = (
            "loginapp" in page.url.lower()
            or "login" in page.url.lower()
            or await page.locator("#btlogin").count() > 0
        )
        if not _needs_login:
            return
        _toggle = page.locator("#bt_login")
        if await _toggle.count() > 0 and await page.locator("#username").count() == 0:
            await _toggle.click()
            await page.wait_for_timeout(800)
        # Angular reactive forms require press_sequentially to trigger ngModel change detection.
        username_input = page.locator("#username")
        await username_input.click()
        await username_input.press_sequentially(settings.merkur_username, delay=50)
        password_input = page.locator("#password")
        await password_input.click()
        await password_input.press_sequentially(settings.merkur_password, delay=50)
        await page.wait_for_timeout(300)
        await page.click("#btlogin")
        try:
            await page.wait_for_url(lambda url: "login/INIT" not in url, timeout=10_000)
        except Exception:
            pass
        await page.wait_for_load_state("networkidle")
        if await page.locator("#btlogin").count() > 0 or "login/INIT" in page.url:
            raise RuntimeError("Merkur login failed: still on login page after submit")
        if fallback_url and "loginapp" in page.url.lower():
            await page.goto(fallback_url, wait_until="networkidle")

    async def _weiter(self, page: Page, step_idx: int) -> None:
        """Click the WEITER button for the given step index (0-based).

        All button[matsteppernext] elements are present in the DOM at once
        (Angular renders every step's content simultaneously). nth(step_idx)
        selects the WEITER for the correct step.
        """
        await page.locator("button[matsteppernext]").nth(step_idx).click()
        await page.wait_for_timeout(800)

    async def _submit(
        self,
        context: BrowserContext,
        page: Page,
        invoice_pdf: str,
        amount: float,
        date: str,
        patient_name: str = "",
        stop_before_submit: bool = False,
    ) -> bool:
        # ── Land on Liferay portal ──────────────────────────────────────────────
        await page.goto(_MERKUR_FORM_URL, wait_until="networkidle")
        await self._dismiss_cookie_banner(page)
        await self._ensure_logged_in(page, fallback_url=_MERKUR_FORM_URL)
        await page.wait_for_timeout(3_000)
        await self._dismiss_cookie_banner(page)

        # ── Open Angular SPA in new tab ─────────────────────────────────────────
        # Confirmed: a[href="/kporclient/einreichung"] opens with target="_blank".
        async with context.expect_page() as new_page_info:
            await page.locator('a[href="/kporclient/einreichung"]').first.click()
        form_page = await new_page_info.value
        await form_page.wait_for_load_state("networkidle")

        # The Angular SPA keeps its own session separate from Liferay.
        await self._dismiss_cookie_banner(form_page)
        await self._ensure_logged_in(
            form_page,
            fallback_url="https://portal.merkur.at/kporclient/einreichung",
        )
        await form_page.wait_for_load_state("networkidle")
        await form_page.wait_for_selector("app-root mat-stepper", timeout=30_000)

        # ── Step 0: Vertrag ─────────────────────────────────────────────────────
        # One radio (mat-radio-group-0), already pre-selected. Just advance.
        await self._weiter(form_page, 0)

        # ── Step 1: Versicherte Person ──────────────────────────────────────────
        # mat-radio-group-1; innerText of mat-radio-button contains "Name (DOB)".
        if patient_name:
            buttons = form_page.locator("mat-radio-button:has(input[name='mat-radio-group-1'])")
            count = await buttons.count()
            matched = False
            for i in range(count):
                if patient_name.lower() in (await buttons.nth(i).inner_text()).lower():
                    await buttons.nth(i).click()
                    matched = True
                    break
            if not matched:
                raise RuntimeError(
                    f"Merkur: '{patient_name}' not found in Versicherte Person list"
                )
        await self._weiter(form_page, 1)

        # ── Step 2: Überweisungskonto ───────────────────────────────────────────
        # mat-radio-group-2; value = IBAN without spaces. First option pre-selected.
        target_iban = settings.merkur_bank_iban.replace(" ", "")
        if target_iban:
            iban_radio = form_page.locator(
                f'input[name="mat-radio-group-2"][value="{target_iban}"]'
            )
            if await iban_radio.count() == 0:
                raise RuntimeError(f"Merkur: IBAN '{target_iban}' not found")
            await iban_radio.click()
        await self._weiter(form_page, 2)

        # ── Step 3: Dateiauswahl ────────────────────────────────────────────────
        # The file input is hidden (0x0); set_input_files works on hidden inputs.
        await form_page.locator("input[type=file]").set_input_files(invoice_pdf)
        await form_page.wait_for_timeout(1_000)
        await self._weiter(form_page, 3)

        # ── Step 4: Zusammenfassung ─────────────────────────────────────────────
        # Confirmed checkbox: #mat-mdc-checkbox-0-input
        chk = form_page.locator("#mat-mdc-checkbox-0-input")
        if not await chk.is_checked():
            await chk.click()

        if stop_before_submit:
            return False

        # ── Submit ──────────────────────────────────────────────────────────────
        # Confirmed button text: 'EINREICHUNG ABSCHLIESSEN'
        await form_page.get_by_role("button", name="EINREICHUNG ABSCHLIESSEN").click()
        await form_page.wait_for_load_state("networkidle", timeout=60_000)

        body = (await form_page.text_content("body") or "").lower()
        return "erfolgreich" in body or "eingereicht" in body or "hochladen" in body


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
