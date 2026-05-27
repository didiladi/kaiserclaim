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
_MERKUR_INBOX_URL = "https://portal.merkur.at/portal/inbox.html#/inbox"
_OEGK_PORTAL_URL = "https://www.oegk.at/kundenportal"

# ---------------------------------------------------------------------------
# Inbox DOM selectors — confirmed by calibrate_merkur_inbox.py (2026-05-22)
# ---------------------------------------------------------------------------
# "Zur Einreichung" button only appears on Ambulante Abrechnungsinformation rows
_INBOX_DOWNLOAD_BTN_SELECTOR = "button[aria-label='Zur Einreichung']"
# Date paragraph within a row (id="documentDatum_N")
_INBOX_DATE_SELECTOR = "p[id^='documentDatum']"
# Year group accordion header — ng-click="inbox.togglePanel(groupDate)"
_INBOX_YEAR_HEADER_SELECTOR = "div.subheader-hover[tabindex='0']"
# Notification popup dismiss button ("Benachrichtigungen aktivieren?")
_INBOX_NOTIFICATION_DISMISS = "button[ng-click*='deactivate'], button.md-button[ng-click*='close'], md-dialog button:first-of-type"

# ---------------------------------------------------------------------------
# Summary SPA selectors — kporclient/einreichungen?gevoid=...
# ---------------------------------------------------------------------------
# URL fragment that identifies the summary SPA (vs. the submission form)
_SUMMARY_URL_FRAGMENT = "kporclient/einreichungen"
# Optional: download the Abrechnung PDF from the summary page
_ABRECHNUNG_DOWNLOAD_BTN = "button:has-text('ABRECHNUNG HERUNTERLADEN')"


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
        debug_pause: bool = False,
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
                    context, page, invoice_pdf, amount, date, patient_name,
                    stop_before_submit, debug_pause,
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

    async def _weiter(self, page: Page) -> None:
        """Click the currently visible WEITER button via JS.

        Playwright's actionability checks block on disabled buttons even when
        Angular's (click) handler would fire. JS element.click() bypasses the
        disabled guard and dispatches the event Angular's stepper.next() listens to.
        """
        await page.evaluate("""() => {
            const btns = [...document.querySelectorAll('button[matsteppernext]')];
            const visible = btns.find(b => {
                const r = b.getBoundingClientRect();
                return r.width > 0 || r.height > 0;
            });
            if (visible) visible.click();
        }""")
        await page.wait_for_timeout(800)

    async def _click_visible_radio(self, page: Page, text: str) -> bool:
        """Click the mat-radio-touch-target of the first visible radio whose text contains *text*.

        Inactive step panels have display:none so getBoundingClientRect() returns zeros —
        that filter ensures we only act on the currently active step's radios.
        Clicking the touch-target fires Angular Material's _onTouchTargetClick BEFORE the
        native input is checked, allowing _onInputInteraction to pass its guard.
        """
        return await page.evaluate("""(text) => {
            for (const btn of document.querySelectorAll('mat-radio-button')) {
                if (!btn.textContent.includes(text)) continue;
                const rect = btn.getBoundingClientRect();
                if (rect.width === 0 && rect.height === 0) continue;
                const target = btn.querySelector('.mat-mdc-radio-touch-target') || btn;
                target.click();
                return true;
            }
            return false;
        }""", text)

    async def _wait_for_visible_radio(self, page: Page, text: str, timeout: int = 5_000) -> None:
        """Wait until a radio button containing *text* has a non-zero bounding rect."""
        await page.wait_for_function("""(text) => {
            for (const btn of document.querySelectorAll('mat-radio-button')) {
                if (!btn.textContent.includes(text)) continue;
                const rect = btn.getBoundingClientRect();
                if (rect.width > 0 || rect.height > 0) return true;
            }
            return false;
        }""", arg=text, timeout=timeout)

    async def _submit(
        self,
        context: BrowserContext,
        page: Page,
        invoice_pdf: str,
        amount: float,
        date: str,
        patient_name: str = "",
        stop_before_submit: bool = False,
        debug_pause: bool = False,
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
        # Wait for Angular to bootstrap. Use mat-step-header (confirmed in calibration DOM
        # dumps) rather than mat-stepper which may not be the outer element tag.
        try:
            await form_page.wait_for_selector("mat-step-header", timeout=30_000)
        except Exception:
            raise RuntimeError(
                f"Merkur: Angular SPA did not render within 30 s "
                f"(tab URL: {form_page.url})"
            )

        # ── Step 0: Vertrag ─────────────────────────────────────────────────────
        # Wait for Angular to finish bootstrapping (WEITER starts disabled).
        await form_page.wait_for_function(
            "() => !document.querySelector('button[matsteppernext]')?.disabled",
            timeout=15_000,
        )
        await self._weiter(form_page)

        if debug_pause:
            print("\n[debug] Now on Person step — browser is paused.")
            print("[debug] Click Resume when done observing.")
            await form_page.pause()

        # ── Step 1: Versicherte Person ──────────────────────────────────────────
        if patient_name:
            # Wait for the step 1 content to finish rendering, then give Angular
            # an extra moment to register click handlers on the radio components.
            # The bounding rect becomes non-zero before Angular finishes wiring up
            # event listeners — without the extra wait, the touch-target click fires
            # before _onTouchTargetClick is bound and nothing happens.
            await self._wait_for_visible_radio(form_page, patient_name, timeout=10_000)
            await form_page.wait_for_timeout(800)
            found = await self._click_visible_radio(form_page, patient_name)
            if not found:
                available = await form_page.evaluate("""() =>
                    [...document.querySelectorAll('mat-radio-button')]
                        .filter(b => { const r = b.getBoundingClientRect();
                                       return r.width > 0 || r.height > 0; })
                        .map(b => b.textContent.trim())
                """)
                raise RuntimeError(
                    f"Merkur: '{patient_name}' not found in Versicherte Person list. "
                    f"Visible options: {available}"
                )
            # Portal auto-advances on person selection; wait for IBAN radios to appear.
            try:
                await self._wait_for_visible_radio(form_page, "AT", timeout=5_000)
            except Exception:
                await self._weiter(form_page)
        else:
            await self._weiter(form_page)

        # ── Step 2: Überweisungskonto ───────────────────────────────────────────
        target_iban = settings.merkur_bank_iban.replace(" ", "")
        if target_iban:
            # The portal displays IBANs with spaces; strip both sides before comparing.
            btn_id = await form_page.evaluate("""(iban) => {
                for (const btn of document.querySelectorAll('mat-radio-button')) {
                    if (!btn.textContent.replace(/\\s/g, '').includes(iban)) continue;
                    const rect = btn.getBoundingClientRect();
                    if (rect.width === 0 && rect.height === 0) continue;
                    return btn.id;
                }
                return null;
            }""", target_iban)
            if not btn_id:
                raise RuntimeError(f"Merkur: IBAN '{target_iban}' not found")
            await form_page.locator(f"#{btn_id} .mat-mdc-radio-touch-target").click(force=True)
            # Wait for file-upload step to appear; fall back to WEITER.
            try:
                await form_page.wait_for_function(
                    "() => { const i = document.querySelector('input[type=file]');"
                    " if (!i) return false;"
                    " const r = i.getBoundingClientRect();"
                    " return r.width > 0 || r.height > 0; }",
                    timeout=3_000,
                )
            except Exception:
                await self._weiter(form_page)
        else:
            await self._weiter(form_page)

        # ── Step 3: Dateiauswahl ────────────────────────────────────────────────
        # The file input is hidden (0x0); set_input_files works on hidden inputs.
        await form_page.locator("input[type=file]").set_input_files(invoice_pdf)
        await form_page.wait_for_timeout(1_000)
        await self._weiter(form_page)

        # ── Step 4: Zusammenfassung ─────────────────────────────────────────────
        # Same touch-target pattern: click mat-mdc-checkbox-touch-target so Angular
        # Material's handler fires before the native checked state changes.
        chk_input = form_page.locator("#mat-mdc-checkbox-0-input")
        if not await chk_input.is_checked():
            await form_page.evaluate("""() => {
                const cb = document.getElementById('mat-mdc-checkbox-0-input')
                    ?.closest('mat-checkbox');
                const target = cb?.querySelector('.mat-mdc-checkbox-touch-target') || cb;
                if (target) target.click();
            }""")
            await form_page.wait_for_timeout(300)

        if stop_before_submit:
            return False

        # ── Submit ──────────────────────────────────────────────────────────────
        # Confirmed button text: 'EINREICHUNG ABSCHLIESSEN'
        await form_page.get_by_role("button", name="EINREICHUNG ABSCHLIESSEN").click()
        await form_page.wait_for_load_state("networkidle", timeout=60_000)

        body = (await form_page.text_content("body") or "").lower()
        return "erfolgreich" in body or "eingereicht" in body or "hochladen" in body


    async def download_inbox_documents(
        self,
        output_dir: str,
        *,
        full_history: bool = False,
    ) -> list[dict]:
        """Download all 'Ambulante Abrechnungsinformation' PDFs from the Merkur Postfach.

        Returns a list of dicts: {title, list_date, pdf_path} for each downloaded document.

        Selectors in this method are provisional — run scripts/calibrate_merkur_inbox.py
        against the live portal and update the _INBOX_* constants at the top of this file.
        """
        _MERKUR_USER_DATA_DIR.mkdir(parents=True, exist_ok=True)
        output = Path(output_dir)
        output.mkdir(parents=True, exist_ok=True)

        downloaded: list[dict] = []

        async with async_playwright() as pw:
            context: BrowserContext = await pw.chromium.launch_persistent_context(
                str(_MERKUR_USER_DATA_DIR),
                headless=True,
                accept_downloads=True,
            )
            page = context.pages[0] if context.pages else await context.new_page()
            try:
                await page.goto(_MERKUR_INBOX_URL, wait_until="networkidle")
                await self._dismiss_cookie_banner(page)
                await self._ensure_logged_in(page, fallback_url=_MERKUR_INBOX_URL)
                await page.wait_for_load_state("networkidle")
                await self._dismiss_notification_popup(page)

                # Wait for the AngularJS inbox to finish rendering its list items.
                # In a fresh (cookie-less) session the SPA makes additional API calls
                # after networkidle; give it up to 20 s before proceeding.
                try:
                    await page.wait_for_selector(
                        "md-list-item", timeout=20_000
                    )
                except Exception:
                    print("[MerkurBot] Inbox list items did not appear — inbox may be empty", flush=True)

                if full_history:
                    await self._expand_all_years(page)
                    # Extra settle time after expanding year groups
                    await page.wait_for_timeout(2_000)

                downloaded = await self._collect_documents(page, output)
            finally:
                await context.close()

        return downloaded

    async def _prime_kporclient_session(self, page: Page) -> None:
        """Navigate to the kporclient SPA once to establish its OAuth session.

        The kporclient SPA runs its own OAuth2 flow independent of the Liferay
        portal session.  Visiting its base URL on a fresh persistent context
        triggers a login redirect; once we log in here the session token is stored
        in the browser context and subsequent gevoid-specific navigations land
        on the correct page without being redirected to login.
        """
        kporclient_base = "https://portal.merkur.at/kporclient/einreichungen"
        try:
            await page.goto(kporclient_base, wait_until="domcontentloaded", timeout=20_000)
        except Exception:
            await page.wait_for_timeout(1_000)
        await self._ensure_logged_in(page, fallback_url=kporclient_base)
        await page.wait_for_load_state("networkidle", timeout=20_000)
        print(f"[MerkurBot] kporclient session primed (url={page.url})", flush=True)

    async def _dismiss_notification_popup(self, page: Page) -> None:
        """Dismiss the 'Benachrichtigungen aktivieren?' dialog if it appears."""
        try:
            # Wait briefly for the dialog to appear
            await page.wait_for_timeout(1_000)
            for sel in _INBOX_NOTIFICATION_DISMISS.split(", "):
                try:
                    btn = page.locator(sel.strip())
                    if await btn.count() > 0 and await btn.first.is_visible():
                        await btn.first.click()
                        await page.wait_for_timeout(500)
                        return
                except Exception:
                    continue
        except Exception:
            pass

    async def _expand_all_years(self, page: Page) -> None:
        """Click all collapsed year accordion headers to expose archived documents."""
        year_headers = await page.query_selector_all(_INBOX_YEAR_HEADER_SELECTOR)
        for header in year_headers:
            try:
                rect = await header.bounding_box()
                if rect and rect["width"] > 0:
                    await header.click()
                    await page.wait_for_timeout(600)
            except Exception:
                continue

    async def _collect_documents(
        self, page: Page, output_dir: Path
    ) -> list[dict]:
        """Enumerate inbox rows and scrape summary data for each Einreichung.

        Clicking 'Zur Einreichung' navigates the current page away from the inbox,
        so instead we extract the geVoId from the AngularJS scope and open each
        summary URL directly in a fresh tab — leaving the inbox page intact.

        Falls back to a click+navigate approach if the AngularJS scope is not
        accessible (e.g. in a non-AngularJS context or after SPA update).
        """
        from services.merkur_summary_scraper import parse_einreichung_text

        results: list[dict] = []
        seen_geschaeftsfaelle: set[str] = set()

        print(f"[MerkurBot] Inbox page URL: {page.url}", flush=True)

        # Extract gevoid + display metadata from AngularJS scope for all rows at once,
        # before navigating anywhere.  The inbox is an AngularJS (1.x) app so
        # angular.element().scope() is always available on the inbox page.
        raw_items: list[dict] = await page.evaluate("""() => {
            const btns = document.querySelectorAll("button[aria-label='Zur Einreichung']");
            return [...btns].map(btn => {
                const row = btn.closest('md-list-item');
                let gevoid = null;
                if (typeof angular !== 'undefined') {
                    try {
                        gevoid = angular.element(row).scope()?.item?.geVoId ?? null;
                    } catch (_) {}
                }
                const label = row?.querySelector('button.md-no-style')
                    ?.getAttribute('aria-label') || '';
                const title = label.split('\\n')[0].trim();
                const dateEl = row?.querySelector('p[id^="documentDatum"]');
                return {
                    gevoid,
                    title: title || 'Ambulante Abrechnungsinformation VN',
                    date: dateEl?.textContent?.trim() || '',
                };
            });
        }""")

        # Dedup gevoids — the inbox renders the same document in multiple sections
        # (e.g. unread + a year group), so the same gevoid can appear several times.
        seen_gevoids: set = set()
        deduped_items = []
        for it in raw_items:
            gv = it.get("gevoid")
            if gv and gv not in seen_gevoids:
                seen_gevoids.add(gv)
                deduped_items.append(it)
            elif not gv:
                deduped_items.append(it)
        raw_items = deduped_items

        print(f"[MerkurBot] Found {len(raw_items)} unique gevoid(s) in inbox", flush=True)

        if not raw_items:
            return results

        # Prime the kporclient SPA session NOW — after we have all gevoids.
        # Priming navigates away from the inbox, so it must happen AFTER gevoid
        # extraction.  Once primed the kporclient OAuth token is stored in the
        # browser context and subsequent gevoid navigations land on the correct
        # page without being redirected to login.
        await self._prime_kporclient_session(page)

        for item in raw_items:
            title = item.get("title", "Ambulante Abrechnungsinformation VN")
            list_date = item.get("date", "")
            gevoid = item.get("gevoid")

            panels_text: list[str] = []

            if not gevoid:
                print(f"[MerkurBot] No gevoid for '{title}' — skipping", flush=True)
                continue

            # Navigate the existing page to the summary URL rather than opening a new
            # tab.  A fresh tab doesn't carry the kporclient SPA session and aborts;
            # the current page already has authenticated cookies for the Liferay portal
            # and the kporclient SPA shares that session.
            summary_url = (
                f"https://portal.merkur.at/kporclient/einreichungen?gevoid={gevoid}"
            )
            try:
                # domcontentloaded avoids ERR_ABORTED from immediate JS redirects
                try:
                    await page.goto(summary_url, wait_until="domcontentloaded", timeout=20_000)
                except Exception:
                    await page.wait_for_timeout(1_000)
                await self._ensure_logged_in(page, fallback_url=summary_url)
                await page.wait_for_load_state("networkidle", timeout=20_000)
                # If OAuth redirected us away from the gevoid URL, navigate back now
                # that the kporclient session is established.
                if f"gevoid={gevoid}" not in page.url:
                    await page.goto(summary_url, wait_until="networkidle", timeout=20_000)
                panels_text = await self._scrape_summary_page(page)
                print(
                    f"[MerkurBot] gevoid={gevoid}: {len(panels_text)} panel(s) scraped",
                    flush=True,
                )
            except Exception as exc:
                print(
                    f"[MerkurBot] Summary page failed (gevoid={gevoid}): {exc}",
                    flush=True,
                )
                continue

            for panel_text in panels_text:
                parsed = parse_einreichung_text(panel_text)
                if not parsed:
                    continue
                if parsed.geschaeftsfall_nr in seen_geschaeftsfaelle:
                    continue
                seen_geschaeftsfaelle.add(parsed.geschaeftsfall_nr)
                results.append({
                    "title": title,
                    "list_date": list_date,
                    "geschaeftsfall_nr": parsed.geschaeftsfall_nr,
                    "document_date": parsed.document_date,
                    "patient_name": parsed.patient_name,
                    "invoice_date": parsed.invoice_date,
                    "invoice_amount": parsed.invoice_amount,
                    "reimbursed_amount": parsed.reimbursed_amount,
                    "result_state": parsed.result_state,
                    "raw_text": parsed.raw_text,
                    "pdf_path": None,
                })

        return results

    async def _scrape_summary_page(self, page: Page) -> list[str]:
        """Return the innerText of each Einreichung panel on the summary SPA.

        Expands all collapsed Angular Material expansion panels first so that
        the Geschäftsfallnummer and line-item details are visible.
        """
        await page.wait_for_load_state("networkidle")
        await page.wait_for_timeout(2_000)

        # Expand all collapsed panels (Angular Material aria-expanded attribute)
        await page.evaluate("""() => {
            for (const h of document.querySelectorAll(
                'mat-expansion-panel-header[aria-expanded="false"], '
                + 'mat-expansion-panel-header:not([aria-expanded="true"])'
            )) {
                try { h.click(); } catch (_) {}
            }
        }""")
        await page.wait_for_timeout(1_000)

        # Collect text per panel.  Use textContent (not innerText) so that collapsed
        # panel bodies are included — innerText respects display:none and returns
        # empty string for hidden Angular Material expansion panel content.
        panels: list[str] = await page.evaluate("""() => {
            const els = document.querySelectorAll('mat-expansion-panel');
            if (els.length > 0) {
                return [...els].map(el => el.textContent || '');
            }
            // Fallback: whole page text if Angular component tags aren't in DOM
            return [document.body.textContent || ''];
        }""")

        return [t for t in panels if t.strip()]


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
