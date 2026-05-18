#!/usr/bin/env python3
"""
Merkur portal calibration harness.

Launches a headed browser, logs in with your stored credentials, walks through
the reimbursement submission flow step by step, snapshots each page to
scripts/.merkur_capture/, and probes candidate selectors at each stage.

Run this ONCE against the live portal to validate (or correct) every selector
used by MerkurBot._submit. The harness stops before the final submit — no
real claim is filed.

Usage:
    cd kaiserclaim
    python scripts/calibrate_merkur.py [--receipt PATH]

Flags:
    --receipt PATH   Path to an invoice PDF/JPG to test the file-upload step.
                     Omit to skip file upload (form selectors are still probed).

Requirements:
    playwright install chromium
    .env must have MERKUR_USERNAME and MERKUR_PASSWORD set.
"""

import argparse
import asyncio
import sys
from pathlib import Path

from playwright.async_api import Page, async_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core.config import get_settings

CAPTURE_DIR = Path(__file__).parent / ".merkur_capture"
PORTAL_URL = "https://www.merkur.at/kundenportal"

# ---------------------------------------------------------------------------
# Candidate selector probes — ordered from most to least specific
# ---------------------------------------------------------------------------

PROBES: dict[str, dict[str, list[str]]] = {
    "login_page": {
        "username": [
            "#username",
            "input[name=username]",
            "input[type=email]",
            "[name=email]",
        ],
        "password": [
            "#password",
            "input[name=password]",
            "input[type=password]",
        ],
        "login_button": [
            "button[type=submit]",
            "button:has-text('Anmelden')",
            "button:has-text('Login')",
            "input[type=submit]",
        ],
        "login_error": [
            ".error",
            ".alert",
            "[class*=error]",
            "[class*=alert]",
            "[role=alert]",
            ".invalid-feedback",
        ],
    },
    "dashboard": {
        "reimbursement_nav": [
            "text=Kostenerstattung",
            "a:has-text('Kostenerstattung')",
            "[href*=kostenerstattung]",
            "[href*=Kostenerstattung]",
        ],
    },
    "submission_list": {
        "new_submission": [
            "text=Neue Einreichung",
            "a:has-text('Neue Einreichung')",
            "button:has-text('Neue Einreichung')",
            "button:has-text('Einreichung')",
        ],
    },
    "submission_form": {
        "file_input": [
            "input[type=file]",
            "input[accept]",
        ],
        "file_trigger": [
            "text=Datei hochladen",
            "button:has-text('hochladen')",
            "label:has-text('hochladen')",
        ],
        "amount": [
            "input[name=amount]",
            "#amount",
            "input[id=amount]",
            "input[placeholder*='Betrag']",
            "input[placeholder*='betrag']",
        ],
        "date": [
            "input[name=date]",
            "input[type=date]",
            "#date",
            "input[id=date]",
        ],
        "submit_button": [
            "button[type=submit]",
            "button:has-text('Einreichen')",
            "button:has-text('Absenden')",
            "button:has-text('Senden')",
        ],
    },
    "confirmation": {
        "success_indicator": [
            "text=erfolgreich",
            "[class*=success]",
            "[role=alert]",
            ".confirmation",
            ".success",
        ],
        "reference_number": [
            "[class*=referenz]",
            "[class*=nummer]",
            "text=Referenz",
        ],
    },
}


async def probe_selectors(page: Page, stage: str) -> dict[str, str | None]:
    """Return field → first matching selector (or None) for the given stage."""
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
            print(f"  MISS {field:<28} (no candidate matched)")
    print()


async def snapshot(page: Page, step: str) -> None:
    CAPTURE_DIR.mkdir(parents=True, exist_ok=True)
    dest = CAPTURE_DIR / f"{step}.html"
    dest.write_text(await page.content(), encoding="utf-8")
    print(f"  [snapshot] {dest}")


async def try_click(page: Page, candidates: list[str], label: str) -> bool:
    for sel in candidates:
        try:
            if await page.locator(sel).count() >= 1:
                await page.locator(sel).first.click()
                print(f"  [click] {label} via {sel!r}")
                return True
        except Exception:
            continue
    return False


async def run(receipt_path: str | None) -> None:
    settings = get_settings()

    print("\nKaiserClaim — Merkur portal calibration harness")
    print(f"Portal  : {PORTAL_URL}")
    print(f"User    : {settings.merkur_username or '(not set — check .env)'}")
    print(f"Captures: {CAPTURE_DIR}/\n")

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=False, slow_mo=200)
        context = await browser.new_context()
        page = await context.new_page()

        # ------------------------------------------------------------------
        # Step 1: navigate to portal
        # ------------------------------------------------------------------
        print("Step 1: navigating to portal…")
        await page.goto(PORTAL_URL, wait_until="networkidle")
        await snapshot(page, "01_login")
        login_results = await probe_selectors(page, "login_page")
        print_probe_results("login_page", login_results)

        # ------------------------------------------------------------------
        # Step 2: login
        # ------------------------------------------------------------------
        print("Step 2: logging in…")
        if not settings.merkur_username:
            print("  MERKUR_USERNAME not set in .env — pausing for manual login.")
            print("  Log in in the browser window, then click Resume in the Inspector.")
            await page.pause()
        else:
            username_sel = login_results.get("username") or "#username"
            password_sel = login_results.get("password") or "#password"
            login_btn_sel = login_results.get("login_button") or "button[type=submit]"
            try:
                await page.fill(username_sel, settings.merkur_username)
                await page.fill(password_sel, settings.merkur_password)
                await page.click(login_btn_sel)
                await page.wait_for_load_state("networkidle")
            except Exception as e:
                print(f"  Automated login failed: {e}")
                print("  Log in manually in the browser, then click Resume.")
                await page.pause()

            # Verify we left the login page
            url = page.url.lower()
            still_on_login = (
                "login" in url
                or "anmelden" in url
                or await page.locator(username_sel).count() > 0
            )
            if still_on_login:
                print(f"  Post-login URL: {page.url}")
                print("  Login may have failed or requires additional steps.")
                print("  Complete login manually in the browser, then click Resume.")
                await page.pause()
            else:
                print(f"  Login succeeded — now at: {page.url}")

        await snapshot(page, "02_dashboard")
        dashboard_results = await probe_selectors(page, "dashboard")
        print_probe_results("dashboard", dashboard_results)

        # ------------------------------------------------------------------
        # Step 3: navigate to Kostenerstattung
        # ------------------------------------------------------------------
        print("Step 3: navigating to Kostenerstattung…")
        nav_candidates = PROBES["dashboard"]["reimbursement_nav"]
        if not await try_click(page, nav_candidates, "Kostenerstattung"):
            print("  Could not find Kostenerstattung nav — pausing.")
            print("  Click 'Kostenerstattung' in the browser, then click Resume.")
            await page.pause()
        await page.wait_for_load_state("networkidle")
        await snapshot(page, "03_kostenerstattung")
        sub_list_results = await probe_selectors(page, "submission_list")
        print_probe_results("submission_list", sub_list_results)

        # ------------------------------------------------------------------
        # Step 4: navigate to Neue Einreichung
        # ------------------------------------------------------------------
        print("Step 4: navigating to Neue Einreichung…")
        new_sub_candidates = PROBES["submission_list"]["new_submission"]
        if not await try_click(page, new_sub_candidates, "Neue Einreichung"):
            print("  Could not find 'Neue Einreichung' — pausing.")
            print("  Click 'Neue Einreichung' in the browser, then click Resume.")
            await page.pause()
        await page.wait_for_load_state("networkidle")
        await snapshot(page, "04_submission_form")
        form_results = await probe_selectors(page, "submission_form")
        print_probe_results("submission_form", form_results)

        # ------------------------------------------------------------------
        # Step 5: fill form — STOP BEFORE SUBMIT
        # ------------------------------------------------------------------
        print("Step 5: filling form (will NOT submit)…")

        if receipt_path:
            file_trigger_candidates = PROBES["submission_form"]["file_trigger"]
            file_input_sel = form_results.get("file_input") or "input[type=file]"
            try:
                await page.wait_for_selector(file_input_sel, timeout=5_000)
                async with page.expect_file_chooser(timeout=5_000) as fc_info:
                    if not await try_click(page, file_trigger_candidates, "file trigger"):
                        print("  File trigger not found — pausing.")
                        await page.pause()
                fc = await fc_info.value
                await fc.set_files(receipt_path)
                print(f"  [file] set to {receipt_path}")
            except Exception as e:
                print(f"  File upload step failed ({e}) — skipping.")
        else:
            print("  No --receipt provided — skipping file upload.")

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

        await snapshot(page, "05_form_filled")
        print("\n  *** STOPPED BEFORE SUBMIT — no claim was filed ***\n")

        # ------------------------------------------------------------------
        # Summary
        # ------------------------------------------------------------------
        all_results = {
            "login_page": login_results,
            "dashboard": dashboard_results,
            "submission_list": sub_list_results,
            "submission_form": form_results,
        }

        print("=" * 62)
        print("CALIBRATION SUMMARY")
        print("Copy confirmed selectors into workers/playwright_bot.py")
        print("=" * 62)
        any_miss = False
        for stage, r in all_results.items():
            for field, sel in r.items():
                if sel:
                    print(f"  OK   {stage}.{field:<30} {sel}")
                else:
                    print(f"  MISS {stage}.{field:<30} check snapshot HTML")
                    any_miss = True

        print(f"\nHTML snapshots saved to: {CAPTURE_DIR}/")
        print("\nNext steps:")
        if any_miss:
            print("  1. Open the MISS snapshots in a browser — inspect the DOM and")
            print("     find the correct selector for each MISS field.")
        print("  1. Update selectors in workers/playwright_bot.py with confirmed values.")
        print("  2. Sanitize snapshots (strip name/policy/address) — see README note.")
        print("  3. Copy sanitized HTML to tests/fixtures/merkur/")
        print("  4. Run: pytest tests/test_merkur_bot.py\n")

        print("Pausing before close — inspect the browser, then click Resume.")
        await page.pause()
        await browser.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Merkur portal calibration harness")
    parser.add_argument(
        "--receipt",
        metavar="PATH",
        help="Invoice PDF/JPG to use for the file-upload step (optional)",
    )
    args = parser.parse_args()
    asyncio.run(run(args.receipt))


if __name__ == "__main__":
    main()
