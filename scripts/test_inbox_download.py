#!/usr/bin/env python3
"""
Manual smoke test for MerkurBot.download_inbox_documents().

Logs into the Merkur Postfach, downloads all Ambulante Abrechnungsinformation
PDFs found in the inbox, and prints a summary. No database writes.

Usage:
    cd kaiserclaim
    python scripts/test_inbox_download.py [--full-history] [--output /tmp/merkur_test]

Options:
    --full-history   also expand year accordion headers to pull archived docs
    --output DIR     where to save downloaded PDFs (default: /tmp/merkur_inbox_test)
    --headed         show the browser window (useful for debugging)
"""
import argparse
import asyncio
import sys
from pathlib import Path

# Allow imports from the project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from workers.playwright_bot import MerkurBot


async def main(output_dir: str, full_history: bool, headed: bool, session_dir: str | None) -> None:
    print(f"[test_inbox_download] output_dir={output_dir}  full_history={full_history}")

    import workers.playwright_bot as bot_module

    # Override the browser session directory so the NAS mount isn't required locally
    if session_dir:
        override = Path(session_dir)
    else:
        # Default: reuse the calibration session next to this script
        override = Path(__file__).parent / ".merkur_session"
    override.mkdir(parents=True, exist_ok=True)
    bot_module._MERKUR_USER_DATA_DIR = override
    print(f"[test_inbox_download] session_dir={override}")

    if headed:
        # Patch launch_persistent_context to run headed
        from playwright.async_api import BrowserContext
        _orig_launch = None

        async def _headed_launch(path, **kwargs):
            kwargs["headless"] = False
            return await _orig_launch(path, **kwargs)

        import playwright.async_api as _pw_api
        # We patch at the chromium level after playwright starts — simpler:
        # just set the env var that Playwright's CLI uses
        import os
        os.environ["HEADED"] = "1"
        # Real headed override via monkeypatching _launch inside the bot
        _real_bot_launch = bot_module.MerkurBot.download_inbox_documents

        async def _headed_download(self, out, *, full_history=False):
            from playwright.async_api import async_playwright as _apw
            bot_module._MERKUR_USER_DATA_DIR.mkdir(parents=True, exist_ok=True)
            output = Path(out)
            output.mkdir(parents=True, exist_ok=True)
            downloaded = []
            async with _apw() as pw:
                context = await pw.chromium.launch_persistent_context(
                    str(bot_module._MERKUR_USER_DATA_DIR),
                    headless=False,
                    accept_downloads=True,
                )
                page = context.pages[0] if context.pages else await context.new_page()
                try:
                    await page.goto(bot_module._MERKUR_INBOX_URL, wait_until="networkidle")
                    await self._dismiss_cookie_banner(page)
                    await self._ensure_logged_in(page, fallback_url=bot_module._MERKUR_INBOX_URL)
                    await page.wait_for_load_state("networkidle")
                    await page.wait_for_timeout(2_000)
                    await self._dismiss_notification_popup(page)
                    if full_history:
                        await self._expand_all_years(page)
                        await page.wait_for_timeout(1_000)
                    downloaded = await self._collect_documents(page, context, output)
                finally:
                    await context.close()
            return downloaded

        bot_module.MerkurBot.download_inbox_documents = _headed_download
        print("[test_inbox_download] Running headed")

    bot = MerkurBot()
    results = await bot.download_inbox_documents(output_dir, full_history=full_history)

    print(f"\n{'='*60}")
    print(f"Scraped {len(results)} Einreichung(en):\n")
    for r in results:
        print(f"  Title:              {r.get('title')}")
        print(f"  List date:          {r.get('list_date')}")
        print(f"  Geschäftsfallnr:    {r.get('geschaeftsfall_nr')}")
        print(f"  Document date:      {r.get('document_date')}")
        print(f"  Patient:            {r.get('patient_name')}")
        print(f"  Invoice date:       {r.get('invoice_date')}")
        print(f"  Invoice amount:     {r.get('invoice_amount')}")
        print(f"  Reimbursed amount:  {r.get('reimbursed_amount')}")
        print(f"  Result state:       {r.get('result_state')}")
        print()

    if not results:
        print("  (none — check the portal manually or run with --full-history)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--full-history", action="store_true",
                        help="expand all year headers to include archived documents")
    parser.add_argument("--output", default="/tmp/merkur_inbox_test",
                        help="directory to save downloaded PDFs")
    parser.add_argument("--headed", action="store_true",
                        help="show browser window")
    parser.add_argument("--session-dir", default=None,
                        help="browser session dir (default: scripts/.merkur_session)")
    args = parser.parse_args()

    asyncio.run(main(args.output, args.full_history, args.headed, args.session_dir))
