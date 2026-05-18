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
            "button[type=submit]", "button:has-text('Anmelden')",
            "button:has-text('Login')", "input[type=submit]",
        ],
    },
    "submission_list": {
        "new_submission": [
            "text=Neue Einreichung",
            "button:has-text('Neue Einreichung')",
            "a:has-text('Neue Einreichung')",
            "button:has-text('Einreichung erstellen')",
            "button:has-text('Neu')",
            "[class*=btn]:has-text('Neu')",
        ],
    },
    "submission_form": {
        "file_input": [
            "input[type=file]", "input[accept]",
        ],
        "file_trigger": [
            "text=Datei hochladen", "button:has-text('hochladen')",
            "label:has-text('hochladen')", "button:has-text('Datei')",
            "label:has-text('Datei')", "[class*=upload]",
        ],
        "amount": [
            "input[name=amount]", "#amount", "input[id=amount]",
            "input[placeholder*='Betrag']", "input[placeholder*='betrag']",
            "input[placeholder*='€']", "input[type=number]",
        ],
        "date": [
            "input[name=date]", "input[type=date]", "#date",
            "input[placeholder*='Datum']", "input[placeholder*='TT.MM']",
        ],
        "submit_button": [
            "button[type=submit]", "button:has-text('Einreichen')",
            "button:has-text('Absenden')", "button:has-text('Senden')",
        ],
    },
    "confirmation": {
        "success_text": [
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


async def _ensure_logged_in(page: Page) -> None:
    """Auto-login using confirmed selectors (#username, #password, #btlogin)."""
    from core.config import get_settings
    settings = get_settings()

    on_login_url = "login" in page.url.lower() or "loginapp" in page.url.lower()
    has_login_form = await page.locator("#btlogin").count() > 0

    if not on_login_url and not has_login_form:
        print("  Session active — skipping login.")
        return

    print("  Login form detected — attempting auto-login…")

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
            await page.fill("#username", settings.merkur_username)
            await page.fill("#password", settings.merkur_password)
            await page.click("#btlogin")
            await page.wait_for_load_state("networkidle")
            await page.wait_for_timeout(2_000)
            print(f"  Auto-login done — now at: {page.url}")
        except Exception as e:
            print(f"  Auto-login failed ({e}) — pausing for manual login.")
            try:
                await page.pause()
            except Exception:
                return

    # If the login redirected away from the form, navigate back
    if "leistungseinreichung" not in page.url:
        print(f"  Navigating back to form from {page.url}…")
        await page.goto(FORM_URL, wait_until="networkidle")
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
        # Step 1: navigate and auto-login if needed
        # ------------------------------------------------------------------
        print("Step 1: navigating to submission form…")
        await page.goto(FORM_URL, wait_until="networkidle")
        await dismiss_cookie_banner(page)
        await page.wait_for_timeout(1_000)
        print(f"  Landed at: {page.url}")

        await _ensure_logged_in(page)

        # Dismiss cookie consent banner before the portlet renders
        await dismiss_cookie_banner(page)

        # Wait for the Liferay/Vue portlet to render
        print("  Waiting for Vue portlet to render…")
        await page.wait_for_load_state("networkidle")
        await page.wait_for_timeout(3_000)
        await dismiss_cookie_banner(page)

        await snapshot(page, "02_submission_list")
        await dump_live_elements(page, "02_submission_list")
        sub_list_results = await probe_selectors(page, "submission_list")
        print_probe_results("submission_list", sub_list_results)

        # ------------------------------------------------------------------
        # Step 2: click "Neue Einreichung"
        # ------------------------------------------------------------------
        print("Step 2: clicking 'Neue Einreichung'…")
        new_sub_sel = sub_list_results.get("new_submission")
        if new_sub_sel:
            await page.locator(new_sub_sel).first.click()
            print(f"  [click] Neue Einreichung via {new_sub_sel!r}")
        else:
            print("  'Neue Einreichung' not found — pausing.")
            print("  Click it in the browser, then Resume.")
            try:
                await page.pause()
            except Exception:
                print("  Browser closed — exiting.")
                return

        await page.wait_for_load_state("networkidle")
        await page.wait_for_timeout(3_000)
        await dismiss_cookie_banner(page)
        await snapshot(page, "03_submission_form")
        await dump_live_elements(page, "03_submission_form")
        form_results = await probe_selectors(page, "submission_form")
        print_probe_results("submission_form", form_results)

        # ------------------------------------------------------------------
        # Step 3: fill form (stop before submit)
        # ------------------------------------------------------------------
        print("Step 3: filling form (will NOT submit)…")

        if receipt_path:
            file_trigger_candidates = PROBES["submission_form"]["file_trigger"]
            file_input_sel = form_results.get("file_input") or "input[type=file]"
            try:
                await page.wait_for_selector(file_input_sel, timeout=5_000)
                async with page.expect_file_chooser(timeout=5_000) as fc_info:
                    found = False
                    for sel in file_trigger_candidates:
                        try:
                            if await page.locator(sel).count() >= 1:
                                await page.locator(sel).first.click()
                                found = True
                                print(f"  [click] file trigger via {sel!r}")
                                break
                        except Exception:
                            continue
                    if not found:
                        print("  File trigger not found — pausing to pick manually.")
                        try:
                            await page.pause()
                        except Exception:
                            print("  Browser closed — exiting.")
                            return
                fc = await fc_info.value
                await fc.set_files(receipt_path)
                print(f"  [file] set to {receipt_path}")
            except Exception as e:
                print(f"  File upload failed ({e}) — skipping.")
        else:
            print("  No --receipt — skipping file upload.")

        amount_sel = form_results.get("amount") or "input[name=amount]"
        date_sel = form_results.get("date") or "input[name=date]"
        for sel, value, label in [
            (amount_sel, "12.34", "amount"),
            (date_sel, "01.01.2025", "date"),
        ]:
            try:
                if await page.locator(sel).count():
                    await page.fill(sel, value)
                    print(f"  [fill] {label} ({sel}) = {value}")
            except Exception as e:
                print(f"  {label} fill failed: {e}")

        await snapshot(page, "04_form_filled")
        print("\n  *** STOPPED BEFORE SUBMIT — no claim was filed ***\n")

        # ------------------------------------------------------------------
        # Summary
        # ------------------------------------------------------------------
        all_results = {
            "submission_list": sub_list_results,
            "submission_form": form_results,
        }

        print("=" * 62)
        print("CALIBRATION SUMMARY")
        print("Update confirmed selectors in workers/playwright_bot.py")
        print("=" * 62)
        any_miss = False
        for stage, r in all_results.items():
            for field, sel in r.items():
                if sel:
                    print(f"  OK   {stage}.{field:<35} {sel}")
                else:
                    print(f"  MISS {stage}.{field:<35} check *_elements.json")
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
            await page.pause()
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
