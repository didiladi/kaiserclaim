#!/usr/bin/env python3
"""
Merkur portal calibration harness.

Launches a headed browser with a persistent session, walks through the
reimbursement submission flow step by step, snapshots each page to
scripts/.merkur_capture/, and probes candidate selectors at each stage.

The session is saved to scripts/.merkur_session/ so subsequent bot runs can
reuse it without logging in again. Run this once to seed the session.

The harness stops before the final submit — no real claim is filed.

Usage:
    cd kaiserclaim
    python scripts/calibrate_merkur.py [--receipt PATH]

Flags:
    --receipt PATH   Invoice PDF/JPG to test the file-upload step (optional).

Requirements:
    playwright install chromium
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

from playwright.async_api import BrowserContext, Page, async_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

CAPTURE_DIR = Path(__file__).parent / ".merkur_capture"
SESSION_DIR = Path(__file__).parent / ".merkur_session"
PORTAL_URL = "https://portal.merkur.at/"
FORM_URL = "https://portal.merkur.at/de/leistungseinreichung"

# ---------------------------------------------------------------------------
# Candidate selector probes (used after the page fully renders)
# ---------------------------------------------------------------------------

PROBES: dict[str, dict[str, list[str]]] = {
    "login_page": {
        "username": [
            "#username", "input[name=username]", "input[type=email]",
            "[name=email]", "input[autocomplete=username]",
        ],
        "password": [
            "#password", "input[name=password]", "input[type=password]",
        ],
        "login_button": [
            "#btlogin", "button[type=submit]", "button:has-text('Anmelden')",
        ],
    },
    "submission_list": {
        # Confirmed: the real link text is "Einreichung starten", opens in new tab.
        "einreichung_starten": [
            'a[href="/kporclient/einreichung"]',
            "a:has-text('Einreichung starten')",
            "a:has-text('Neue Einreichung')",
        ],
    },
    # The Angular SPA steps below probe the new tab (form_page).
    "step1_person": {
        "person_radio_group": [
            'mat-radio-button[name="mat-radio-group-1"]',
            'input[name="mat-radio-group-1"]',
        ],
        "weiter_button": [
            "button.mat-stepper-next",
            "button[matsteppernext]",
            "button:has-text('WEITER')",
        ],
    },
    "step2_iban": {
        "iban_radio_group": [
            'mat-radio-button[name="mat-radio-group-2"]',
            'input[name="mat-radio-group-2"]',
        ],
        "weiter_button": [
            "button.mat-stepper-next",
            "button[matsteppernext]",
            "button:has-text('WEITER')",
        ],
    },
    "step3_upload": {
        "file_input": [
            "input[type=file]", "input[accept]",
        ],
        "file_trigger": [
            "button:has-text('hochladen')", "button:has-text('Datei')",
            "label:has-text('hochladen')", "label:has-text('Datei')",
            "[class*=upload]",
        ],
        "weiter_button": [
            "button.mat-stepper-next",
            "button[matsteppernext]",
            "button:has-text('WEITER')",
        ],
    },
    "step4_summary": {
        "confirm_checkbox": [
            "mat-checkbox input[type=checkbox]",
            "input[type=checkbox]",
            "[class*=confirm] input",
        ],
        "submit_button": [
            "button[type=submit]", "button:has-text('Einreichen')",
            "button:has-text('Absenden')", "button:has-text('Senden')",
        ],
    },
    "confirmation": {
        "success_indicator": [
            "text=erfolgreich", "text=eingereicht", "[class*=success]",
            "[role=alert]", ".confirmation",
        ],
    },
}


async def dismiss_cookie_banner(page: Page) -> None:
    """Click 'Ablehnen' on the CCM19 cookie consent banner if it appears."""
    for sel in ["button[aria-label='Ablehnen']", "button[aria-label='Alles akzeptieren']"]:
        try:
            btn = page.locator(sel)
            if await btn.count() > 0 and await btn.first.is_visible():
                await btn.first.click()
                print(f"  [cookie] dismissed banner via {sel!r}")
                await page.wait_for_timeout(500)
                return
        except Exception:
            continue


async def probe_selectors(page: Page, stage: str) -> dict[str, str | None]:
    results: dict[str, str | None] = {}
    for field, candidates in PROBES.get(stage, {}).items():
        winner = None
        for sel in candidates:
            try:
                if await page.locator(sel).count() == 1:
                    winner = sel
                    break
            except Exception:
                continue
        results[field] = winner
    return results


def print_probe_results(stage: str, results: dict[str, str | None]) -> None:
    print(f"\n{'='*62}")
    print(f"  SELECTOR PROBE: {stage}")
    print(f"{'='*62}")
    for field, selector in results.items():
        if selector:
            print(f"  OK   {field:<28} {selector}")
        else:
            print(f"  MISS {field:<28} (inspect below ↓)")
    print()


async def snapshot(page: Page, step: str) -> None:
    CAPTURE_DIR.mkdir(parents=True, exist_ok=True)
    dest = CAPTURE_DIR / f"{step}.html"
    dest.write_text(await page.content(), encoding="utf-8")
    print(f"  [snapshot] {dest}")


async def dump_live_elements(page: Page, label: str) -> None:
    """Extract all visible interactive elements from the live DOM and print them."""
    elements = await page.evaluate("""() => {
        const els = document.querySelectorAll(
            'input:not([type=hidden]), button, select, textarea, [role=button]'
        );
        const results = [];
        for (const el of els) {
            const rect = el.getBoundingClientRect();
            if (rect.width === 0 && rect.height === 0) continue;
            results.push({
                tag:         el.tagName.toLowerCase(),
                type:        el.type || '',
                id:          el.id || '',
                name:        el.name || '',
                cls:         el.className?.toString().substring(0, 60) || '',
                placeholder: el.placeholder || '',
                ariaLabel:   el.getAttribute('aria-label') || '',
                text:        el.innerText?.trim().substring(0, 80) || '',
            });
        }
        return results;
    }""")

    print(f"\n  --- Live DOM elements on {label} ---")
    for el in elements:
        parts = [f"<{el['tag']}"]
        if el["type"]:
            parts.append(f" type={el['type']!r}")
        if el["id"]:
            parts.append(f" id={el['id']!r}")
        if el["name"]:
            parts.append(f" name={el['name']!r}")
        if el["placeholder"]:
            parts.append(f" placeholder={el['placeholder']!r}")
        if el["ariaLabel"]:
            parts.append(f" aria-label={el['ariaLabel']!r}")
        if el["text"]:
            parts.append(f">  {el['text']!r}")
        else:
            parts.append(">")
        print("   ", "".join(parts))
    print()

    # Save as JSON for reference
    dest = CAPTURE_DIR / f"{label.replace(' ', '_')}_elements.json"
    CAPTURE_DIR.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(elements, ensure_ascii=False, indent=2))
    print(f"  [elements] {dest}")


async def _ensure_logged_in(page: Page, *, fallback_url: str | None = None) -> None:
    """Auto-login using confirmed selectors (#username, #password, #btlogin).

    After login the portal redirects via the 'goto' param embedded in loginapp.html.
    Pass fallback_url only when the redirect is not guaranteed to land in the right place.
    """
    from core.config import get_settings
    settings = get_settings()

    on_login_url = "loginapp" in page.url.lower() or "login" in page.url.lower()
    has_login_form = await page.locator("#btlogin").count() > 0

    if not on_login_url and not has_login_form:
        print("  Session active — skipping login.")
        return

    print(f"  Login form detected at {page.url} — attempting auto-login…")

    # The Anmelden toggle may need to be clicked to reveal the form
    toggle = page.locator("#bt_login")
    if await toggle.count() > 0 and await page.locator("#username").count() == 0:
        await toggle.click()
        await page.wait_for_timeout(800)

    if not settings.merkur_username:
        print("  MERKUR_USERNAME not set — pausing for manual login.")
        try:
            await page.pause()
        except Exception:
            return
    else:
        try:
            # Angular reactive forms need press_sequentially (fires keydown/input/keyup)
            # rather than fill() which may not trigger ngModel change detection.
            username_input = page.locator("#username")
            await username_input.click()
            await username_input.press_sequentially(settings.merkur_username, delay=50)
            password_input = page.locator("#password")
            await password_input.click()
            await password_input.press_sequentially(settings.merkur_password, delay=50)
            await page.wait_for_timeout(300)
            await page.click("#btlogin")
            # Wait for Angular router to leave the INIT state (URL fragment changes on success).
            try:
                await page.wait_for_url(
                    lambda url: "login/INIT" not in url,
                    timeout=10_000,
                )
            except Exception:
                pass
            await page.wait_for_load_state("networkidle")
            print(f"  Auto-login done — now at: {page.url}")
        except Exception as e:
            print(f"  Auto-login failed ({e}) — pausing for manual login.")
            try:
                await page.pause()
            except Exception:
                return

    # If still on loginapp after all that, pause for the user to intervene.
    if "loginapp" in page.url.lower():
        print("  Login did not succeed — pausing for manual login. Click Resume when done.")
        try:
            await page.pause()
        except Exception:
            return

    if fallback_url and "loginapp" in page.url.lower():
        print(f"  Still on login page — navigating directly to {fallback_url}…")
        await page.goto(fallback_url, wait_until="networkidle")
        await dismiss_cookie_banner(page)
        await page.wait_for_timeout(2_000)
        print(f"  Now at: {page.url}")


async def run(receipt_path: str | None) -> None:
    SESSION_DIR.mkdir(parents=True, exist_ok=True)
    CAPTURE_DIR.mkdir(parents=True, exist_ok=True)

    print("\nKaiserClaim — Merkur portal calibration harness")
    print(f"Portal  : {PORTAL_URL}")
    print(f"Session : {SESSION_DIR}/  (reused across runs)")
    print(f"Captures: {CAPTURE_DIR}/\n")

    async with async_playwright() as pw:
        context: BrowserContext = await pw.chromium.launch_persistent_context(
            str(SESSION_DIR),
            headless=False,
            slow_mo=150,
            accept_downloads=True,
        )
        page = context.pages[0] if context.pages else await context.new_page()

        # ------------------------------------------------------------------
        # Step 1: navigate to Liferay portal and auto-login if needed
        # ------------------------------------------------------------------
        print("Step 1: navigating to submission form…")
        await page.goto(FORM_URL, wait_until="networkidle")
        await dismiss_cookie_banner(page)
        await page.wait_for_timeout(1_000)
        print(f"  Landed at: {page.url}")

        await _ensure_logged_in(page, fallback_url=FORM_URL)
        await dismiss_cookie_banner(page)

        print("  Waiting for Liferay portlet to render…")
        await page.wait_for_load_state("networkidle")
        await page.wait_for_timeout(3_000)
        await dismiss_cookie_banner(page)

        await snapshot(page, "02_portal_dashboard")
        await dump_live_elements(page, "02_portal_dashboard")
        portal_results = await probe_selectors(page, "submission_list")
        print_probe_results("submission_list (Liferay portal)", portal_results)

        # ------------------------------------------------------------------
        # Step 2: click "Einreichung starten" → intercept new Angular tab
        # ------------------------------------------------------------------
        print("Step 2: clicking 'Einreichung starten' (opens new tab)…")
        einreichung_sel = portal_results.get("einreichung_starten")
        if einreichung_sel:
            async with context.expect_page() as new_page_info:
                await page.locator(einreichung_sel).first.click()
                print(f"  [click] Einreichung starten via {einreichung_sel!r}")
        else:
            print("  'Einreichung starten' not found — pausing.")
            print("  Click it in the browser (it opens a new tab), then Resume.")
            try:
                async with context.expect_page() as new_page_info:
                    await page.pause()
            except Exception:
                print("  Browser closed — exiting.")
                await context.close()
                return

        form_page = await new_page_info.value
        print(f"  New tab URL: {form_page.url}")
        await form_page.wait_for_load_state("networkidle")

        # The Angular SPA has its own session — the Liferay cookie does not carry over.
        # Login here if the new tab landed on loginapp.html.
        await dismiss_cookie_banner(form_page)
        await _ensure_logged_in(form_page, fallback_url="https://portal.merkur.at/kporclient/einreichung")
        await form_page.wait_for_load_state("networkidle")
        print(f"  After login — form tab URL: {form_page.url}")

        # Wait for Angular mat-stepper to bootstrap
        print("  Waiting for Angular mat-stepper to render…")
        try:
            await form_page.wait_for_selector("app-root mat-stepper", timeout=30_000)
            print("  mat-stepper found — Angular bootstrapped.")
        except Exception:
            print("  mat-stepper not found within 30 s — dumping DOM anyway.")

        await snapshot(form_page, "03_step1_person")
        await dump_live_elements(form_page, "03_step1_person")
        step1_results = await probe_selectors(form_page, "step1_person")
        print_probe_results("step1_person (Angular SPA)", step1_results)

        # ------------------------------------------------------------------
        # Step 3: Versicherte Person — show radio options
        # ------------------------------------------------------------------
        print("Step 3: probing Versicherte Person radio options…")
        radio_labels = form_page.locator('mat-radio-button[name="mat-radio-group-1"] label')
        count = await radio_labels.count()
        print(f"  Found {count} person radio(s):")
        for i in range(count):
            txt = (await radio_labels.nth(i).inner_text()).strip()
            print(f"    [{i}] {txt!r}")

        # Select the first option for calibration purposes (no real claim).
        if count > 0:
            await radio_labels.first.click()
            print("  [click] Selected first Versicherte Person for calibration.")

        weiter_sel = step1_results.get("weiter_button") or "button.mat-stepper-next"
        await form_page.locator(weiter_sel).first.click()
        print(f"  [click] WEITER via {weiter_sel!r}")
        await form_page.wait_for_timeout(1_000)

        # ------------------------------------------------------------------
        # Step 4: Überweisungskonto
        # ------------------------------------------------------------------
        print("Step 4: probing Überweisungskonto radio options…")
        await snapshot(form_page, "04_step2_iban")
        await dump_live_elements(form_page, "04_step2_iban")
        step2_results = await probe_selectors(form_page, "step2_iban")
        print_probe_results("step2_iban (Angular SPA)", step2_results)

        iban_inputs = form_page.locator('input[name="mat-radio-group-2"]')
        iban_count = await iban_inputs.count()
        print(f"  Found {iban_count} IBAN radio(s):")
        for i in range(iban_count):
            val = await iban_inputs.nth(i).get_attribute("value") or ""
            checked = await iban_inputs.nth(i).is_checked()
            print(f"    [{i}] value={val!r}  checked={checked}")

        weiter2_sel = step2_results.get("weiter_button") or "button.mat-stepper-next"
        await form_page.locator(weiter2_sel).first.click()
        print(f"  [click] WEITER via {weiter2_sel!r}")
        await form_page.wait_for_timeout(1_000)

        # ------------------------------------------------------------------
        # Step 5: File upload
        # ------------------------------------------------------------------
        print("Step 5: probing file upload step…")
        await snapshot(form_page, "05_step3_upload")
        await dump_live_elements(form_page, "05_step3_upload")
        step3_results = await probe_selectors(form_page, "step3_upload")
        print_probe_results("step3_upload (Angular SPA)", step3_results)

        if receipt_path:
            file_trigger_candidates = PROBES["step3_upload"]["file_trigger"]
            try:
                await form_page.wait_for_selector("input[type=file]", timeout=5_000)
                async with form_page.expect_file_chooser(timeout=5_000) as fc_info:
                    found = False
                    for sel in file_trigger_candidates:
                        try:
                            if await form_page.locator(sel).count() >= 1:
                                await form_page.locator(sel).first.click()
                                found = True
                                print(f"  [click] file trigger via {sel!r}")
                                break
                        except Exception:
                            continue
                    if not found:
                        print("  File trigger not found — pausing to pick manually.")
                        try:
                            await form_page.pause()
                        except Exception:
                            print("  Browser closed — exiting.")
                            await context.close()
                            return
                fc = await fc_info.value
                await fc.set_files(receipt_path)
                print(f"  [file] set to {receipt_path}")
                await form_page.wait_for_timeout(1_000)
            except Exception as e:
                print(f"  File upload failed ({e}) — skipping.")
        else:
            print("  No --receipt — skipping file upload; WEITER will likely be disabled.")

        weiter3_sel = step3_results.get("weiter_button") or "button.mat-stepper-next"
        try:
            btn3 = form_page.locator(weiter3_sel).first
            if await btn3.is_enabled():
                await btn3.click()
                print(f"  [click] WEITER via {weiter3_sel!r}")
                await form_page.wait_for_timeout(1_000)
            else:
                print("  WEITER disabled (no file uploaded) — skipping step 5 WEITER.")
        except Exception as e:
            print(f"  Step 5 WEITER failed: {e}")

        # ------------------------------------------------------------------
        # Step 6: Zusammenfassung / confirmation checkbox
        # ------------------------------------------------------------------
        print("Step 6: probing Zusammenfassung (confirmation) step…")
        await snapshot(form_page, "06_step4_summary")
        await dump_live_elements(form_page, "06_step4_summary")
        step4_results = await probe_selectors(form_page, "step4_summary")
        print_probe_results("step4_summary (Angular SPA)", step4_results)

        print("\n  *** STOPPED BEFORE FINAL SUBMIT — no claim was filed ***\n")

        # ------------------------------------------------------------------
        # Summary
        # ------------------------------------------------------------------
        all_results = {
            "portal_dashboard / submission_list": portal_results,
            "step1_person": step1_results,
            "step2_iban": step2_results,
            "step3_upload": step3_results,
            "step4_summary": step4_results,
        }

        print("=" * 62)
        print("CALIBRATION SUMMARY")
        print("Update confirmed selectors in workers/playwright_bot.py")
        print("=" * 62)
        any_miss = False
        for stage, r in all_results.items():
            for field, sel in r.items():
                if sel:
                    print(f"  OK   {stage}.{field:<40} {sel}")
                else:
                    print(f"  MISS {stage}.{field:<40} check *_elements.json")
                    any_miss = True

        print(f"\nHTML snapshots : {CAPTURE_DIR}/*.html")
        print(f"Element dumps  : {CAPTURE_DIR}/*_elements.json")
        if any_miss:
            print("\nFor MISS fields: open the *_elements.json file for the step,")
            print("find the element you need, and build a selector from its id/name/text.")

        print("\nNext steps:")
        print("  1. Update TODO selectors in workers/playwright_bot.py.")
        print("  2. Strip PII from HTML captures; copy to tests/fixtures/merkur/.")
        print("  3. Update test constants in tests/test_merkur_bot.py.")
        print("  4. pytest tests/test_merkur_bot.py\n")

        print("Pausing before close — inspect the browser, then click Resume.")
        try:
            await form_page.pause()
        except Exception:
            pass
        await context.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Merkur portal calibration harness")
    parser.add_argument(
        "--receipt", metavar="PATH",
        help="Invoice PDF/JPG to test the file-upload step (optional)",
    )
    args = parser.parse_args()
    asyncio.run(run(args.receipt))


if __name__ == "__main__":
    main()
