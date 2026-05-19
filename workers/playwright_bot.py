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
        await page.fill("#username", settings.merkur_username)
        await page.fill("#password", settings.merkur_password)
        await page.click("#btlogin")
        await page.wait_for_load_state("networkidle")
        await page.wait_for_timeout(2_000)
        if await page.locator("#btlogin").count() > 0:
            raise RuntimeError("Merkur login failed: still on login page after submit")
        if fallback_url and "loginapp" in page.url.lower():
            await page.goto(fallback_url, wait_until="networkidle")

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
        # Land on the Liferay portal page that hosts the "Einreichung starten" link.
        await page.goto(_MERKUR_FORM_URL, wait_until="networkidle")
        await self._dismiss_cookie_banner(page)
        await self._ensure_logged_in(page, fallback_url=_MERKUR_FORM_URL)

        # Wait for the Liferay portlet to finish rendering.
        await page.wait_for_timeout(3_000)
        await self._dismiss_cookie_banner(page)

        # "Einreichung starten" opens the Angular SPA in a new tab (target="_blank").
        # Confirmed selector: a[href="/kporclient/einreichung"]
        async with context.expect_page() as new_page_info:
            await page.locator('a[href="/kporclient/einreichung"]').first.click()
        form_page = await new_page_info.value
        await form_page.wait_for_load_state("networkidle")

        # The Angular SPA has its own session — the Liferay cookie does not carry over.
        # After clicking the link the new tab lands on loginapp.html; login there too.
        await self._dismiss_cookie_banner(form_page)
        # The goto param in loginapp.html redirects back to /kporclient/einreichung automatically.
        await self._ensure_logged_in(form_page, fallback_url="https://portal.merkur.at/kporclient/einreichung")
        await form_page.wait_for_load_state("networkidle")

        # Wait for Angular to bootstrap — the loading spinner disappears from app-root.
        await form_page.wait_for_selector("app-root mat-stepper", timeout=30_000)

        # ── Step 1: Versicherte Person ──────────────────────────────────────────
        # Confirmed: name="mat-radio-group-1"; label text contains patient name + DOB.
        # If patient_name is given, select the matching radio; otherwise use pre-checked.
        if patient_name:
            radio_labels = form_page.locator('mat-radio-button[name="mat-radio-group-1"] label')
            count = await radio_labels.count()
            matched = False
            for i in range(count):
                label_text = (await radio_labels.nth(i).inner_text()).strip()
                if patient_name.lower() in label_text.lower():
                    await radio_labels.nth(i).click()
                    matched = True
                    break
            if not matched:
                raise RuntimeError(
                    f"Merkur: Versicherte Person '{patient_name}' not found in radio list"
                )

        await form_page.locator("button.mat-stepper-next").first.click()
        await form_page.wait_for_timeout(800)

        # ── Step 2: Überweisungskonto ───────────────────────────────────────────
        # Confirmed: name="mat-radio-group-2"; value is IBAN without spaces.
        # If merkur_bank_iban is set, select it; otherwise the pre-selected account is used.
        target_iban = settings.merkur_bank_iban.replace(" ", "")
        if target_iban:
            iban_radio = form_page.locator(
                f'input[name="mat-radio-group-2"][value="{target_iban}"]'
            )
            if await iban_radio.count() == 0:
                raise RuntimeError(
                    f"Merkur: IBAN '{target_iban}' not found in Überweisungskonto list"
                )
            await iban_radio.click()

        await form_page.locator("button.mat-stepper-next").first.click()
        await form_page.wait_for_timeout(800)

        # ── Step 3: File upload ─────────────────────────────────────────────────
        # TODO: replace with confirmed selector after calibration of this step.
        await form_page.wait_for_selector("input[type=file]", timeout=10_000)
        async with form_page.expect_file_chooser() as fc_info:
            # Try known Angular upload trigger patterns; fall back to direct input.
            for _trigger in [
                "button:has-text('hochladen')", "button:has-text('Datei')",
                "label:has-text('hochladen')", "[class*=upload]",
            ]:
                try:
                    if await form_page.locator(_trigger).count() > 0:
                        await form_page.locator(_trigger).first.click()
                        break
                except Exception:
                    continue
            else:
                await form_page.locator("input[type=file]").first.click()
        file_chooser = await fc_info.value
        await file_chooser.set_files(invoice_pdf)
        await form_page.wait_for_timeout(1_000)

        await form_page.locator("button.mat-stepper-next").first.click()
        await form_page.wait_for_timeout(800)

        # ── Step 4: Zusammenfassung — confirmation checkbox ─────────────────────
        # TODO: replace with confirmed selector after calibration.
        for _chk_sel in [
            "mat-checkbox input[type=checkbox]",
            "input[type=checkbox]",
            "[class*=confirm] input",
        ]:
            try:
                chk = form_page.locator(_chk_sel)
                if await chk.count() > 0 and not await chk.first.is_checked():
                    await chk.first.click()
                    break
            except Exception:
                continue

        if stop_before_submit:
            return False

        # ── Step 5: Final submit ────────────────────────────────────────────────
        # TODO: replace with confirmed submit-button selector after calibration.
        await form_page.locator("button[type=submit]").last.click()
        await form_page.wait_for_load_state("networkidle")

        # TODO: replace with confirmed success element after calibration.
        body = (await form_page.text_content("body") or "").lower()
        return "erfolgreich" in body or "eingereicht" in body


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
