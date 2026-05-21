#!/usr/bin/env python3
"""
Merkur bot dry run — walks the full wizard, stops before submit.

Uses the calibration browser session (scripts/.merkur_session/) so the
Angular SPA login cookies are already present.  Runs headed so you can
watch each step.  No claim is filed.

Usage:
    cd kaiserclaim
    python scripts/dry_run_merkur.py --receipt /path/to/receipt.pdf \
        [--patient "Dieter Ladenhauf"] [--iban AT232081500044776086]
"""

import argparse
import asyncio
import sys
from pathlib import Path

from playwright.async_api import async_playwright, BrowserContext

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

SESSION_DIR = Path(__file__).parent / ".merkur_session"


async def run(receipt: str, patient: str, iban: str, debug_pause: bool = False) -> None:
    # Import here so get_settings() picks up .env from the project root.
    from workers.playwright_bot import MerkurBot

    print("\nKaiserClaim — Merkur bot dry run (stop_before_submit=True)")
    print(f"Session : {SESSION_DIR}/")
    print(f"Receipt : {receipt}")
    print(f"Patient : {patient or '(first match / pre-selected)'}")
    print(f"IBAN    : {iban or '(pre-selected)'}\n")

    bot = MerkurBot()

    # Monkey-patch the session dir and headless flag for the dry run so we
    # reuse the calibration cookies and can observe the browser.
    from playwright.async_api import async_playwright as _ap
    from workers import playwright_bot as _mod

    original_user_data = _mod._MERKUR_USER_DATA_DIR
    _mod._MERKUR_USER_DATA_DIR = SESSION_DIR

    # Override setting for this run only.
    from core.config import get_settings
    settings = get_settings()
    original_iban = settings.merkur_bank_iban
    if iban:
        settings.merkur_bank_iban = iban

    SESSION_DIR.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as pw:
        context: BrowserContext = await pw.chromium.launch_persistent_context(
            str(SESSION_DIR),
            headless=False,
            slow_mo=400,
            accept_downloads=True,
        )
        page = context.pages[0] if context.pages else await context.new_page()
        try:
            result = await bot._submit(
                context=context,
                page=page,
                invoice_pdf=receipt,
                amount=0.0,
                date="01.01.2025",
                patient_name=patient,
                stop_before_submit=True,
                debug_pause=debug_pause,
            )
            if result is False:
                print("\n✓  Dry run complete — stopped before submit.  No claim was filed.")
            else:
                print(f"\n  _submit returned: {result!r}")
        except Exception as exc:
            print(f"\n✗  Error: {exc}")
            raise
        finally:
            _mod._MERKUR_USER_DATA_DIR = original_user_data
            settings.merkur_bank_iban = original_iban

        print("\nInspect the browser, then close the window to exit.")
        try:
            await page.pause()
        except Exception:
            pass
        await context.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Merkur bot dry run")
    parser.add_argument("--receipt", required=True, help="Path to receipt PDF/JPG")
    parser.add_argument("--patient", default="", help="Patient name substring to match")
    parser.add_argument("--iban", default="", help="IBAN to select (without spaces)")
    parser.add_argument("--debug-pause", action="store_true",
                        help="Pause in Playwright Inspector before step 0 so you can manually interact")
    args = parser.parse_args()

    receipt = str(Path(args.receipt).expanduser().resolve())
    if not Path(receipt).exists():
        print(f"Error: receipt file not found: {receipt}")
        sys.exit(1)

    asyncio.run(run(receipt, args.patient, args.iban, args.debug_pause))


if __name__ == "__main__":
    main()
