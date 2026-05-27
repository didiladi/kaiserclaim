#!/usr/bin/env python3
"""
Merkur Postfach (inbox) calibration harness.

You drive the browser; the harness snapshots the DOM and dumps interactive
elements so the selectors in workers/playwright_bot.py can be confirmed and
updated.

Usage:
    cd kaiserclaim
    python scripts/calibrate_merkur_inbox.py [--full-history]

Requirements:
    python -m playwright install chromium
    .env must contain MERKUR_USERNAME and MERKUR_PASSWORD
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

from playwright.async_api import BrowserContext, Page, async_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.config import get_settings

settings = get_settings()

CAPTURE_DIR = Path(__file__).parent / ".merkur_capture"
SESSION_DIR = Path(__file__).parent / ".merkur_session"
INBOX_URL = "https://portal.merkur.at/portal/inbox.html#/inbox"


# ---------------------------------------------------------------------------
# DOM capture helpers (shared with calibrate_merkur.py)
# ---------------------------------------------------------------------------

async def snapshot(page: Page, step: str) -> None:
    CAPTURE_DIR.mkdir(parents=True, exist_ok=True)
    dest = CAPTURE_DIR / f"{step}.html"
    dest.write_text(await page.content(), encoding="utf-8")
    print(f"  [snapshot] {dest}")


async def dump_elements(page: Page, step: str) -> list[dict]:
    elements: list[dict] = await page.evaluate("""() => {
        const els = document.querySelectorAll(
            'button, a[href], [role=button], [role=listitem], mat-list-item, '
            + 'mat-expansion-panel-header, [class*="inbox"], [class*="item"]'
        );
        const results = [];
        for (const el of els) {
            const rect = el.getBoundingClientRect();
            if (rect.width === 0 && rect.height === 0) continue;
            results.push({
                tag:       el.tagName.toLowerCase(),
                id:        el.id || '',
                cls:       (el.className?.toString() || '').substring(0, 120),
                ariaLabel: el.getAttribute('aria-label') || '',
                title:     el.getAttribute('title') || '',
                href:      el.getAttribute('href') || '',
                text:      (el.innerText || '').trim().substring(0, 120),
            });
        }
        return results;
    }""")

    print(f"\n  --- Elements on {step} ({len(elements)} visible) ---")
    for el in elements:
        parts = [f"<{el['tag']}"]
        for attr in ("id", "href"):
            if el[attr]:
                parts.append(f" {attr}={el[attr]!r}")
        if el["ariaLabel"]:
            parts.append(f" aria-label={el['ariaLabel']!r}")
        if el["title"]:
            parts.append(f" title={el['title']!r}")
        if el["cls"]:
            parts.append(f" class={el['cls']!r}")
        if el["text"]:
            parts.append(f">  {el['text']!r}")
        else:
            parts.append(">")
        print("   ", "".join(parts))

    CAPTURE_DIR.mkdir(parents=True, exist_ok=True)
    dest = CAPTURE_DIR / f"{step}_elements.json"
    dest.write_text(json.dumps(elements, ensure_ascii=False, indent=2))
    print(f"  [elements] {dest}\n")
    return elements


async def pause_step(page: Page, step: str, instruction: str) -> None:
    print(f"\n{'─' * 62}")
    print(f"  {step}")
    print(f"{'─' * 62}")
    print(f"  {instruction}")
    print("  When done → click Resume in the Playwright Inspector bar.")
    try:
        await page.pause()
    except Exception:
        print("  (pause skipped)")


# ---------------------------------------------------------------------------
# Main calibration flow
# ---------------------------------------------------------------------------

async def run(full_history: bool) -> None:
    SESSION_DIR.mkdir(parents=True, exist_ok=True)
    CAPTURE_DIR.mkdir(parents=True, exist_ok=True)

    print("\nKaiserClaim — Merkur Postfach inbox calibration")
    print(f"Inbox URL: {INBOX_URL}")
    print(f"Session  : {SESSION_DIR}/")
    print(f"Captures : {CAPTURE_DIR}/\n")

    async with async_playwright() as pw:
        context: BrowserContext = await pw.chromium.launch_persistent_context(
            str(SESSION_DIR),
            headless=False,
            slow_mo=0,
            accept_downloads=True,
        )
        page = context.pages[0] if context.pages else await context.new_page()

        # ── Navigate to inbox ──────────────────────────────────────────────
        print(f"Navigating to {INBOX_URL}…")
        await page.goto(INBOX_URL, wait_until="networkidle")
        print(f"  Landed at: {page.url}")

        await pause_step(
            page, "STEP 1 — Login (if needed)",
            "If you see a login form: fill credentials and log in.\n"
            "  If already logged in: just click Resume.",
        )
        await page.wait_for_load_state("networkidle")
        await page.wait_for_timeout(2_000)

        await snapshot(page, "07_inbox_ungelesen")
        await dump_elements(page, "07_inbox_ungelesen")

        print("\n  KEY THINGS TO IDENTIFY:")
        print("  1. Selector for each inbox item row (the whole row)")
        print("  2. Sub-selector for the title text within a row")
        print("  3. Sub-selector for the date text within a row")
        print("  4. Sub-selector for the download icon button (left of archive icon)")
        print("  5. Selector for year accordion headers (to expand archived sections)")

        if full_history:
            await pause_step(
                page, "STEP 2 — Expand a year section",
                "Click on one of the year headers (e.g. '2026') to expand it.\n"
                "  When expanded: click Resume.",
            )
            await snapshot(page, "08_inbox_year_expanded")
            await dump_elements(page, "08_inbox_year_expanded")

        await pause_step(
            page, "STEP 3 — Click the download icon on a document",
            "Find an 'Ambulante Abrechnungsinformation' row.\n"
            "  Click its download icon (green icon left of the archive icon).\n"
            "  Observe whether it triggers a file download or opens a PDF tab.\n"
            "  Then click Resume.",
        )
        await page.wait_for_timeout(1_000)
        await snapshot(page, "09_inbox_after_download_click")
        await dump_elements(page, "09_inbox_after_download_click")

        print("\n" + "=" * 62)
        print("CALIBRATION COMPLETE")
        print("=" * 62)
        print(f"\nHTML snapshots : {CAPTURE_DIR}/07_*.html  08_*.html  09_*.html")
        print(f"Element dumps  : {CAPTURE_DIR}/*_elements.json")
        print("\nNext steps:")
        print("  1. Review terminal output above — note confirmed selectors.")
        print("  2. Update _INBOX_*_SELECTOR constants in workers/playwright_bot.py.")
        print("  3. Strip PII from *.html; copy to tests/fixtures/merkur/.")
        print("  4. pytest tests/test_merkur_bot.py")

        print("\nInspect the browser if you like, then close the window.")
        try:
            await page.pause()
        except Exception:
            pass
        await context.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Calibrate Merkur Postfach inbox selectors")
    parser.add_argument("--full-history", action="store_true", help="Also calibrate year-expansion")
    args = parser.parse_args()
    asyncio.run(run(args.full_history))


if __name__ == "__main__":
    main()
