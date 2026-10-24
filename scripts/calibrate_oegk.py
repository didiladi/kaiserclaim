#!/usr/bin/env python3
"""
meine ÖGK calibration harness — manual-click mode.

Mirrors scripts/calibrate_merkur.py. You drive the browser (including the
ID-Austria 2FA login); the harness pauses at each step, snapshots the live DOM
and dumps all visible interactive elements to JSON. The selectors in
OegkBot (workers/playwright_bot.py) are uncalibrated guesses until this has
been run once against the live portal.

It stops BEFORE the final submit: no claim is filed.

Usage (needs a display):
    cd kaiserclaim
    python scripts/calibrate_oegk.py [--url https://...]

--url is the meine ÖGK web entry point. The default is the meine ÖGK start page
("Zur Anmeldung" leads to the ID Austria login).

Captures land in scripts/.oegk_capture/ (gitignored, may contain PII).
The browser session is kept in scripts/.oegk_session/ (gitignored, auth cookies).

After the run, paste the terminal output to Claude Code to update the selectors
and the success check in OegkBot, strip PII from the snapshots, and add them as
fixtures under tests/fixtures/oegk/.
"""

import argparse
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
PORTAL_URL = "https://meine.oegk.at/cdscontent/?contentid=10007.883235&portal=oegkportal"

_cm.CAPTURE_DIR = CAPTURE_DIR
snapshot = _cm.snapshot
dump_elements = _cm.dump_elements
pause_step = _cm.pause_step


async def save_downloads(page, label: str) -> None:
    """Save any file the portal offers while a step is paused (PII: stays in CAPTURE_DIR)."""
    async def _save(download) -> None:
        n = len(list(CAPTURE_DIR.glob(f"{label}_*"))) + 1  # same suggested name every time
        target = CAPTURE_DIR / f"{label}_{n}_{download.suggested_filename}"
        await download.save_as(str(target))
        print(f"  Saved download: {target.name}")

    async def _save_pdf_response(response) -> None:
        # PDFs that open in the browser's viewer never fire a download event
        try:
            if "application/pdf" not in response.headers.get("content-type", ""):
                return
            n = len(list(CAPTURE_DIR.glob(f"{label}_inline_*.pdf"))) + 1
            target = CAPTURE_DIR / f"{label}_inline_{n}.pdf"
            target.write_bytes(await response.body())
            print(f"  Saved inline PDF: {target.name} (from {response.url.split('?')[0]})")
        except Exception as exc:  # response bodies can be gone after navigation
            print(f"  (could not save PDF response: {exc})")

    page.context.on("page", lambda p: p.on("download", lambda d: asyncio.ensure_future(_save(d))))
    page.on("download", lambda d: asyncio.ensure_future(_save(d)))
    page.context.on("response", lambda r: asyncio.ensure_future(_save_pdf_response(r)))


async def phase_lookup(page) -> None:
    """Only the 'Eingereichte Rechnungen' list, details and PDF downloads."""
    await pause_step(
        page, "LOOKUP 1 — Liste der Einreichungen",
        "Rechnung & Beitrag → 'Eingereichte Rechnungen abfragen'. Pick the\n"
        "  Wahlarzt / Wahltherapeut tab, click Weiter and WAIT until the list with\n"
        "  your 2 entries is shown. Only then click Resume (the last run captured\n"
        "  the page before the list had loaded).",
    )
    await snapshot(page, "L1_list")
    await dump_elements(page, "L1_list")

    await pause_step(
        page, "LOOKUP 2 — PDF icon in the list",
        "Click the PDF icon of the FIRST entry. Whether it downloads or opens in a\n"
        "  tab, the file is saved to the capture dir. If a tab opened, close it\n"
        "  and return to the list before clicking Resume.",
    )
    await snapshot(page, "L2_after_pdf_icon")

    await pause_step(
        page, "LOOKUP 3 — PDF-Bestätigung on the details page",
        "Back on the list: click 'Details' of the FIRST entry, then click\n"
        "  'PDF-Bestätigung'. Check whether it is the same file as the list icon.",
    )
    await snapshot(page, "L3_details")
    await dump_elements(page, "L3_details")

    await pause_step(
        page, "LOOKUP 4 — Second entry",
        "Go back and repeat the PDF download for the SECOND entry (either way).",
    )


async def phase_review(page) -> None:
    """The submit form past the last 'Weiter': person selection and review page."""
    await pause_step(
        page, "REVIEW 1 — Form up to Mitversicherte",
        "Rechnung einreichen: enter a date, Weiter, pick Wahlarzt / Wahltherapeut,\n"
        "  upload a test file (Hinzufügen). Then click 'für Mitversicherte' and WAIT\n"
        "  until the input for the insured person appears.\n"
        "  Do NOT type anything yet.",
    )
    await snapshot(page, "R1_mitversicherte")
    await dump_elements(page, "R1_mitversicherte")

    await pause_step(
        page, "REVIEW 2 — Enter the insured person",
        "Type the Sozialversicherungsnummer of one insured person (e.g. your wife)\n"
        "  and note what the portal does with it (does it show the name back? an\n"
        "  error for a wrong number? a 'Prüfen' button?). Use the same format the\n"
        "  field's placeholder asks for (NNNNTTMMJJ).",
    )
    await snapshot(page, "R2_person_selected")
    await dump_elements(page, "R2_person_selected")

    await pause_step(
        page, "REVIEW 3 — Review page",
        "Select the first Email and Telefon and click 'Weiter'. The next page\n"
        "  should summarise the claim before it is sent. WAIT until it is shown.\n"
        "  *** STOP HERE: do NOT click any final send / Absenden / Einreichen button ***.\n"
        "  Note the exact label of that button.",
    )
    await snapshot(page, "R3_review")
    await dump_elements(page, "R3_review")


PHASES = {"lookup": phase_lookup, "review": phase_review}


async def run(portal_url: str, phase: str = "all") -> None:
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
        await save_downloads(page, "download")

        print("Navigating to portal…")
        await page.goto(portal_url, wait_until="networkidle")
        print(f"  Landed at: {page.url}")

        await pause_step(
            page, "STEP 1 — Login (ID Austria 2FA)",
            "Click 'Zur Anmeldung', log in at ID Austria (user/password, Identify,\n"
            "  then the 2nd factor on the phone) until meine ÖGK shows its start page\n"
            "  (…/gpmsv/?LO=1…). If already logged in: just click Resume.\n"
            "  NOTE the URL of an expired session (OegkBot needs to detect it).",
        )
        print(f"  URL after login: {page.url}")
        await snapshot(page, "01_start")
        await dump_elements(page, "01_start")

        if phase != "all":
            await PHASES[phase](page)
            print("\nPhase done — *** no claim was filed ***")
            print(f"Captures: {CAPTURE_DIR}/")
            await context.close()
            return

        await pause_step(
            page, "STEP 2 — Rechnung einreichen: Behandlungsdatum",
            "Go to 'Rechnung und Beitrag' then 'Rechnung einreichen (Kostenerstattung\n"
            "  anfordern)' (…/gpmsv/cashback.xhtml). Enter a date in the Tag/Monat/Jahr\n"
            "  field but do NOT click Weiter yet.",
        )
        await snapshot(page, "02_cashback_date")
        await dump_elements(page, "02_cashback_date")

        await pause_step(
            page, "STEP 3a — Art der Leistung",
            "Click Weiter. Note the type tabs (Wahlarzt/Wahltherapeut, Zahnarzt,\n"
            "  Fahrtkosten, Heilbehelfe, Zeckenschutzimpfung). Select Wahlarzt /\n"
            "  Wahltherapeut. Pharmacy receipts (Medikamente) go to Merkur only,\n"
            "  so only the doctor types matter.",
        )
        await snapshot(page, "03a_type")
        await dump_elements(page, "03a_type")

        await pause_step(
            page, "STEP 3b — Beilagen (upload)",
            "Browse, pick a test file, click 'hinzufügen'. Note what happens after\n"
            "  (file list, remove button, size/type limits).\n"
            "  *** DO NOT click the final submit button ***.",
        )
        await snapshot(page, "03b_attachments")
        await dump_elements(page, "03b_attachments")

        await pause_step(
            page, "STEP 3c — Für wen reichen Sie ein?",
            "Click through the tabs 'für Mich' / 'für Mitversicherte' / 'als\n"
            "  Erwachsenenvertreter'. On 'für Mitversicherte' select a child or your\n"
            "  wife and note how the person is listed (name only? Vers.-Nr.?).\n"
            "  The patient has to be matched to the KaiserClaim FamilyMember.",
        )
        await snapshot(page, "03c_for_whom")
        await dump_elements(page, "03c_for_whom")

        await pause_step(
            page, "STEP 3d — Bankdaten + Kontaktdaten",
            "Meine Bankdaten is prefilled. Choose the first Email and the first\n"
            "  Telefon in the dropdowns. Stop at the last page before the final\n"
            "  submit (Weiter / Absenden).  *** DO NOT submit ***.",
        )
        await snapshot(page, "03d_contact")
        await dump_elements(page, "03d_contact")

        await pause_step(
            page, "STEP 4 — Success signal (read-only)",
            "OegkBot needs a success signal and a reference number after submit.\n"
            "  If you have a PREVIOUS submission, open its confirmation / detail page\n"
            "  now so the real wording can be captured. Otherwise just click Resume.",
        )
        await snapshot(page, "04_confirmation_reference")
        await dump_elements(page, "04_confirmation_reference")

        await pause_step(
            page, "STEP 5 — Eingereichte Rechnungen abfragen",
            "Go to 'Rechnung & Beitrag' → 'Eingereichte Rechnungen abfragen'\n"
            "  (…/vsInfo/views/KE/). Pick the type tab (Wahlarzt / Wahltherapeut),\n"
            "  check Von-/Bis-Datum (default = last 12 months) and click Weiter.\n"
            "  You should land on 'Liste der Einreichungen' (einreichungListe.xhtml).\n"
            "  Note: the list has sections (e.g. 'erstattete Einreichungen'). Are there\n"
            "  other sections for pending / rejected claims? What do they look like?",
        )
        await snapshot(page, "05_einreichungen_liste")
        await dump_elements(page, "05_einreichungen_liste")

        await pause_step(
            page, "STEP 6 — Details + PDF download",
            "Click 'Details' on one entry, then go back and click the PDF icon of an\n"
            "  entry (the file is saved to the capture dir automatically). Repeat the\n"
            "  PDF download for the 2nd entry.\n"
            "  Note: does Details show the original invoice amount (the list only shows\n"
            "  the refund)? Is there a Vorgangs-/Aktenzahl? Does the PDF text repeat the\n"
            "  invoice date and amount? (that decides how PDFs get matched to invoices).",
        )
        await snapshot(page, "06_einreichung_details")
        await dump_elements(page, "06_einreichung_details")

        print("=" * 62)
        print("CALIBRATION COMPLETE — *** no claim was filed ***")
        print("=" * 62)
        print(f"\nHTML snapshots : {CAPTURE_DIR}/*.html")
        print(f"Element dumps  : {CAPTURE_DIR}/*_elements.json")
        print("\nNext steps:")
        print("  1. Paste this terminal output to Claude Code.")
        print("  2. OegkBot is rewritten against the captured meine ÖGK screens.")
        print("  3. Strip PII from *.html; copy to tests/fixtures/oegk/.")
        print("  4. Add fixture tests mirroring tests/test_merkur_bot.py.\n")

        print("Inspect the browser if you like, then close the window.")
        try:
            await page.pause()
        except Exception:
            pass
        await context.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[1] if __doc__ else None)
    parser.add_argument("--url", default=PORTAL_URL, help="meine ÖGK entry URL")
    parser.add_argument(
        "--phase", choices=["all", *PHASES], default="all",
        help="'lookup' = list + PDF download only, 'review' = form up to the review page",
    )
    args = parser.parse_args()
    asyncio.run(run(args.url, args.phase))


if __name__ == "__main__":
    main()
