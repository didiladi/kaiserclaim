#!/usr/bin/env python3
"""
Live check of OegkBot.download_refunds against meine ÖGK: downloads the refund PDFs
into a folder and prints what the parser makes of each. Nothing is stored in the
database and nothing is sent to the API.

Needs a display (headed browser, ID Austria 2FA on first use or when the session expired).

    cd kaiserclaim
    python scripts/oegk_download_refunds.py [--since DD.MM.YYYY] [--out DIR]

PDFs contain personal data: the default folder scripts/.oegk_capture/refunds/ is gitignored.
"""
import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.oegk_result_parser import parse_oegk_pdf  # noqa: E402
from workers.playwright_bot import OegkBot  # noqa: E402


async def main(out: Path, since: str | None) -> None:
    paths = await OegkBot().download_refunds(str(out), since)
    print(f"Downloaded {len(paths)} PDF(s) to {out}/")
    for path in paths:
        r = parse_oegk_pdf(path)
        if r is None:
            print(f"  {Path(path).name}: NOT recognised as a refund confirmation")
        else:  # no name, no SV number: safe to paste back
            print(
                f"  {Path(path).name}: invoice {r.invoice_amount:.2f} EUR, refund {r.reimbursed_amount:.2f} EUR, "
                f"service {r.service_from:%d.%m.%Y}-{r.service_to:%d.%m.%Y}, paid {r.payout_date:%d.%m.%Y}"
            )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    parser.add_argument("--since", help="Von-Datum DD.MM.YYYY (portal default: last 12 months)")
    parser.add_argument("--out", type=Path, default=Path(__file__).parent / ".oegk_capture" / "refunds")
    args = parser.parse_args()
    asyncio.run(main(args.out, args.since))
