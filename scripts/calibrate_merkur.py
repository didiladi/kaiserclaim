#!/usr/bin/env python3
"""
Merkur portal calibration harness — manual-click mode.

You drive the browser; the harness pauses at each wizard step, snapshots
the live DOM, and dumps all visible interactive elements to JSON.  After
you finish, paste the terminal output here and the selectors get updated
in workers/playwright_bot.py.

The browser session is saved so you stay logged in across runs.

Usage:
    cd kaiserclaim
    python scripts/calibrate_merkur.py

Requirements:
    python -m playwright install chromium
"""

import asyncio
import json
import sys
from pathlib import Path

from playwright.async_api import BrowserContext, Page, async_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

CAPTURE_DIR = Path(__file__).parent / ".merkur_capture"
SESSION_DIR = Path(__file__).parent / ".merkur_session"
FORM_URL = "https://portal.merkur.at/de/leistungseinreichung"


# ---------------------------------------------------------------------------
# DOM capture helpers
# ---------------------------------------------------------------------------

async def snapshot(page: Page, step: str) -> None:
    CAPTURE_DIR.mkdir(parents=True, exist_ok=True)
    dest = CAPTURE_DIR / f"{step}.html"
    dest.write_text(await page.content(), encoding="utf-8")
    print(f"  [snapshot] {dest}")


async def dump_elements(page: Page, step: str) -> list[dict]:
    """Extract all visible interactive elements and save to JSON."""
    elements: list[dict] = await page.evaluate("""() => {
        const els = document.querySelectorAll(
            'input:not([type=hidden]), button, select, textarea, a[href], '
            + '[role=button], mat-radio-button, mat-checkbox'
        );
        const results = [];
        for (const el of els) {
            const rect = el.getBoundingClientRect();
            if (rect.width === 0 && rect.height === 0) continue;
            results.push({
                tag:         el.tagName.toLowerCase(),
                type:        el.type || '',
                id:          el.id || '',
                name:        el.name || el.getAttribute('name') || '',
                cls:         (el.className?.toString() || '').substring(0, 80),
                placeholder: el.placeholder || '',
                ariaLabel:   el.getAttribute('aria-label') || '',
                href:        el.getAttribute('href') || '',
                value:       el.value || '',
                checked:     el.checked || false,
                text:        (el.innerText || '').trim().substring(0, 100),
            });
        }
        return results;
    }""")

    print(f"\n  --- Elements on {step} ---")
    for el in elements:
        parts = [f"<{el['tag']}"]
        for attr in ("type", "id", "name", "href", "value"):
            if el[attr]:
                parts.append(f" {attr}={el[attr]!r}")
        if el["placeholder"]:
            parts.append(f" placeholder={el['placeholder']!r}")
        if el["ariaLabel"]:
            parts.append(f" aria-label={el['ariaLabel']!r}")
        if el["checked"]:
            parts.append(" checked")
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
    """Print instruction, pause for user interaction, then capture."""
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

async def run() -> None:
    SESSION_DIR.mkdir(parents=True, exist_ok=True)
    CAPTURE_DIR.mkdir(parents=True, exist_ok=True)

    print("\nKaiserClaim — Merkur portal calibration harness")
    print("You drive the browser.  The harness snapshots DOM at each step.")
    print(f"Session : {SESSION_DIR}/")
    print(f"Captures: {CAPTURE_DIR}/\n")

    async with async_playwright() as pw:
        context: BrowserContext = await pw.chromium.launch_persistent_context(
            str(SESSION_DIR),
            headless=False,
            slow_mo=0,
            accept_downloads=True,
        )
        page = context.pages[0] if context.pages else await context.new_page()

        # ── Step 1: portal landing / login ─────────────────────────────────
        print("Navigating to portal…")
        await page.goto(FORM_URL, wait_until="networkidle")
        print(f"  Landed at: {page.url}")

        await pause_step(
            page, "STEP 1 — Login (if needed)",
            "If you see a login form: fill in your credentials and log in.\n"
            "  If you're already logged in: just click Resume.",
        )
        await snapshot(page, "01_portal_dashboard")
        await dump_elements(page, "01_portal_dashboard")

        # ── Step 2: open Angular SPA in new tab ────────────────────────────
        n_tabs_before = len(context.pages)

        await pause_step(
            page, "STEP 2 — Open submission form",
            "Click 'Einreichung starten'.  It opens a NEW TAB.\n"
            "  Switch to the new tab, complete the login there if prompted,\n"
            "  wait for the wizard to appear, then click Resume.",
        )

        # Detect which tab is the Angular SPA
        all_pages = context.pages
        if len(all_pages) > n_tabs_before:
            form_page = all_pages[-1]
        else:
            form_page = page
        print(f"  Active tab: {form_page.url}")

        await snapshot(form_page, "02_step1_person")
        await dump_elements(form_page, "02_step1_person")

        # ── Step 3: Versicherte Person ──────────────────────────────────────
        await pause_step(
            form_page, "STEP 3 — Versicherte Person",
            "Select your name in the radio list, then click Resume\n"
            "  (do NOT click WEITER yet).",
        )
        await snapshot(form_page, "03_step1_person_selected")
        await dump_elements(form_page, "03_step1_person_selected")

        # ── Step 4: WEITER → Überweisungskonto ─────────────────────────────
        await pause_step(
            form_page, "STEP 4 — Überweisungskonto",
            "Click WEITER, then select your bank account in the next step.\n"
            "  When the account is selected, click Resume\n"
            "  (do NOT click WEITER yet).",
        )
        await snapshot(form_page, "04_step2_iban_selected")
        await dump_elements(form_page, "04_step2_iban_selected")

        # ── Step 5: WEITER → file upload ───────────────────────────────────
        await pause_step(
            form_page, "STEP 5 — File upload",
            "Click WEITER, then upload a receipt file in the next step.\n"
            "  When the file is attached (before clicking WEITER), click Resume.",
        )
        await snapshot(form_page, "05_step3_upload")
        await dump_elements(form_page, "05_step3_upload")

        # ── Step 6: WEITER → Zusammenfassung ───────────────────────────────
        await pause_step(
            form_page, "STEP 6 — Zusammenfassung",
            "Click WEITER.  On the summary page: tick the confirmation checkbox.\n"
            "  When the checkbox is ticked, click Resume\n"
            "  *** DO NOT click the final submit button ***.",
        )
        await snapshot(form_page, "06_step4_summary")
        await dump_elements(form_page, "06_step4_summary")

        # ── Done ───────────────────────────────────────────────────────────
        print("=" * 62)
        print("CALIBRATION COMPLETE — *** no claim was filed ***")
        print("=" * 62)
        print(f"\nHTML snapshots : {CAPTURE_DIR}/*.html")
        print(f"Element dumps  : {CAPTURE_DIR}/*_elements.json")
        print("\nNext steps:")
        print("  1. Paste this terminal output to Claude Code.")
        print("  2. Selectors in workers/playwright_bot.py get updated.")
        print("  3. Strip PII from *.html; copy to tests/fixtures/merkur/.")
        print("  4. pytest tests/test_merkur_bot.py\n")

        print("Inspect the browser if you like, then close the window.")
        try:
            await form_page.pause()
        except Exception:
            pass
        await context.close()


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
