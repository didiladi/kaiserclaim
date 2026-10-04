#!/usr/bin/env python3
"""
ÖGK Kundenportal calibration harness — manual-click mode.

Mirrors scripts/calibrate_merkur.py. You drive the browser (including the
ID-Austria 2FA login); the harness pauses at each step, snapshots the live DOM
and dumps all visible interactive elements to JSON. The selectors in
OegkBot (workers/playwright_bot.py) are uncalibrated guesses until this has
been run once against the live portal.

It stops BEFORE the final submit: no claim is filed.

Usage (needs a display):
    cd kaiserclaim
    python scripts/calibrate_oegk.py

Captures land in scripts/.oegk_capture/ (gitignored, may contain PII).
The browser session is kept in scripts/.oegk_session/ (gitignored, auth cookies).

After the run, paste the terminal output to Claude Code to update the selectors
and the success check in OegkBot, strip PII from the snapshots, and add them as
fixtures under tests/fixtures/oegk/.
"""

import asyncio
import sys
from pathlib import Path

from playwright.async_api import BrowserContext, async_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

# Reuse the DOM-capture helpers from the Merkur harness, redirected to our dirs.
import calibrate_merkur as _cm  # noqa: E402

CAPTURE_DIR = Path(__file__).parent / ".oegk_capture"
SESSION_DIR = Path(__file__).parent / ".oegk_session"
PORTAL_URL = "https://www.oegk.at/kundenportal"

_cm.CAPTURE_DIR = CAPTURE_DIR
snapshot = _cm.snapshot
dump_elements = _cm.dump_elements
pause_step = _cm.pause_step


async def run() -> None:
    SESSION_DIR.mkdir(parents=True, exist_ok=True)
    CAPTURE_DIR.mkdir(parents=True, exist_ok=True)

    print("\nKaiserClaim — ÖGK portal calibration harness")
    print("You drive the browser.  The harness snapshots DOM at each step.")
    print(f"Session : {SESSION_DIR}/")
    print(f"Captures: {CAPTURE_DIR}/\n")

    async with async_playwright() as pw:
        context: BrowserContext = await pw.chromium.launch_persistent_context(
            str(SESSION_DIR),
            headless=False,
            accept_downloads=True,
        )
        page = context.pages[0] if context.pages else await context.new_page()

        print("Navigating to portal…")
        await page.goto(PORTAL_URL, wait_until="networkidle")
        print(f"  Landed at: {page.url}")

        await pause_step(
            page, "STEP 1 — Login (ID Austria 2FA)",
            "Log in and complete 2FA until the portal start page is shown.\n"
            "  If you are already logged in: just click Resume.\n"
            "  NOTE the URL you land on after login (OegkBot checks for\n"
            "  'login' / 'anmelden' in the URL to detect an expired session).",
        )
        print(f"  URL after login: {page.url}")
        await snapshot(page, "01_start")
        await dump_elements(page, "01_start")

        await pause_step(
            page, "STEP 2 — Neue Einreichung",
            "Navigate to the screen for a NEW submission (Leistungsabrechnung →\n"
            "  Neue Einreichung, or whatever it is called today).\n"
            "  Note the exact menu labels; OegkBot currently clicks\n"
            "  'text=Leistungsabrechnung' then 'text=Neue Einreichung'.",
        )
        await snapshot(page, "02_new_submission")
        await dump_elements(page, "02_new_submission")

        await pause_step(
            page, "STEP 3 — Upload + form fields",
            "Attach a receipt file and fill in amount and date (and any other\n"
            "  mandatory fields: patient, provider, Rechnungsnummer, IBAN …).\n"
            "  Write down every field that is required.\n"
            "  *** DO NOT click the final submit button ***.",
        )
        await snapshot(page, "03_filled_form")
        await dump_elements(page, "03_filled_form")

        await pause_step(
            page, "STEP 4 — Success signal (read-only)",
            "OegkBot decides success by looking for the word 'eingereicht' in the\n"
            "  page body after submit. If you have a PREVIOUS submission, open its\n"
            "  confirmation / detail page now so the real wording can be captured.\n"
            "  Otherwise just click Resume.",
        )
        await snapshot(page, "04_confirmation_reference")
        await dump_elements(page, "04_confirmation_reference")

        await pause_step(
            page, "STEP 5 — Abrechnungen / refund documents",
            "Open the list of settlements ('Meine Abrechnungen'). Find a refund\n"
            "  document, if any.  Look for anything that ties a document to a\n"
            "  specific submission (date, amount, Rechnungsnummer, Aktenzahl):\n"
            "  poll_oegk_refund can only advance an invoice automatically when\n"
            "  exactly one is in flight, so a matching key would remove that limit.",
        )
        await snapshot(page, "05_settlements")
        await dump_elements(page, "05_settlements")

        print("=" * 62)
        print("CALIBRATION COMPLETE — *** no claim was filed ***")
        print("=" * 62)
        print(f"\nHTML snapshots : {CAPTURE_DIR}/*.html")
        print(f"Element dumps  : {CAPTURE_DIR}/*_elements.json")
        print("\nNext steps:")
        print("  1. Paste this terminal output to Claude Code.")
        print("  2. OegkBot selectors + success check get updated.")
        print("  3. Strip PII from *.html; copy to tests/fixtures/oegk/.")
        print("  4. Add fixture tests mirroring tests/test_merkur_bot.py.\n")

        print("Inspect the browser if you like, then close the window.")
        try:
            await page.pause()
        except Exception:
            pass
        await context.close()


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
