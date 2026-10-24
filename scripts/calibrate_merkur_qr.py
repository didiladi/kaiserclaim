#!/usr/bin/env python3
"""
Merkur 'QR-Code-Einreichung' calibration harness: manual-click mode.

The Merkur wizard has a separate "QR-Code-Einreichung" entry that MerkurBot never
uses (it uploads the receipt photo through the generic flow). Merkur's advisor says
the QR route is the easiest way to submit pharmacy receipts, so before building on it
we need to see what it asks for: a photo of the QR code, the decoded text, a camera,
extra attachments (e.g. the ÖGK refund PDF)?

It stops BEFORE the final submit: no claim is filed.

Usage (needs a display; reuses the Merkur session of scripts/calibrate_merkur.py):
    cd kaiserclaim
    python scripts/calibrate_merkur_qr.py

Captures land in scripts/.merkur_capture/qr_* (gitignored, may contain PII).
"""
import asyncio
import sys
from pathlib import Path

from playwright.async_api import BrowserContext, async_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import calibrate_merkur as _cm  # noqa: E402

snapshot = _cm.snapshot
dump_elements = _cm.dump_elements
pause_step = _cm.pause_step


async def run() -> None:
    _cm.SESSION_DIR.mkdir(parents=True, exist_ok=True)
    _cm.CAPTURE_DIR.mkdir(parents=True, exist_ok=True)

    print("\nKaiserClaim: Merkur QR-Code-Einreichung calibration harness")
    print("You drive the browser.  The harness snapshots DOM at each step.")
    print(f"Captures: {_cm.CAPTURE_DIR}/qr_*\n")

    async with async_playwright() as pw:
        context: BrowserContext = await pw.chromium.launch_persistent_context(
            str(_cm.SESSION_DIR), headless=False, accept_downloads=True,
        )
        page = context.pages[0] if context.pages else await context.new_page()
        await page.goto(_cm.FORM_URL, wait_until="networkidle")
        n_tabs_before = len(context.pages)

        await pause_step(
            page, "STEP 1: Open the wizard",
            "Log in if asked, click 'Einreichung starten' (opens a NEW TAB) and wait\n"
            "  until the wizard shows its first step. Do not start a submission yet.",
        )
        form_page = context.pages[-1] if len(context.pages) > n_tabs_before else page
        print(f"  Active tab: {form_page.url}")

        await pause_step(
            form_page, "STEP 2: QR-Code-Einreichung",
            "Click 'QR-Code-Einreichung' in the side menu and wait for it to load.\n"
            "  Note: does it ask for a photo of the QR code, a camera scan, or the\n"
            "  decoded text? Is the same patient / IBAN / contract selection needed?",
        )
        await snapshot(form_page, "qr_01_landing")
        await dump_elements(form_page, "qr_01_landing")

        await pause_step(
            form_page, "STEP 3: Provide a receipt",
            "Submit the QR the way the page asks for it, using a pharmacy receipt you\n"
            "  have not claimed yet (or a test one). If a step needs the amount or\n"
            "  date typed in, note whether the QR fills it in by itself.\n"
            "  Continue until the page after the QR was read. *** Do NOT send ***.",
        )
        await snapshot(form_page, "qr_02_after_qr")
        await dump_elements(form_page, "qr_02_after_qr")

        await pause_step(
            form_page, "STEP 4: Attachments + summary",
            "Is there a place to attach more files (the ÖGK refund PDF, the photo of\n"
            "  the receipt)? Try to add one. Continue to the summary / final page.\n"
            "  Note the exact label of the final button.  *** Do NOT click it ***.",
        )
        await snapshot(form_page, "qr_03_summary")
        await dump_elements(form_page, "qr_03_summary")

        print("=" * 62)
        print("CALIBRATION COMPLETE: *** no claim was filed ***")
        print("=" * 62)
        print(f"\nCaptures: {_cm.CAPTURE_DIR}/qr_*.html and qr_*_elements.json")
        print("Next: tell Claude Code it is done; strip PII before anything is added as a fixture.\n")
        try:
            await form_page.pause()
        except Exception:
            pass
        await context.close()


if __name__ == "__main__":
    asyncio.run(run())
