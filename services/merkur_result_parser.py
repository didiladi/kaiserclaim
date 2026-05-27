"""
Parser for Merkur 'Ambulante Abrechnungsinformation VN' result PDFs.

These PDFs are placed in the Merkur Postfach after a claim is processed.
They carry the reimbursement decision (approved amount or rejection) and
enough metadata to match the document back to the original uploaded receipt.
"""
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from pdfminer.high_level import extract_text as pdfminer_extract_text

from models.domain import MerkurResultState


# ---------------------------------------------------------------------------
# Patterns
# ---------------------------------------------------------------------------

# "Graz, 2025-10-08" or "Graz, 08.10.2025"
_DOC_DATE_ISO = re.compile(r"Graz,\s*(\d{4})-(\d{2})-(\d{2})")
_DOC_DATE_DE = re.compile(r"Graz,\s*(\d{2})\.(\d{2})\.(\d{4})")
# "Bearbeitung vom 08.10.2025"
_DOC_DATE_BEARBEITUNG = re.compile(r"Bearbeitung\s+vom\s+(\d{2})\.(\d{2})\.(\d{4})")

# "Geschäftsfall: 202501798104"
_GESCHAEFTSFALL = re.compile(r"Gesch[äa]ftsfall[:\s]+(\d+)")

# pdfminer extracts the PDF table columns non-linearly, so we match each field
# individually instead of as a single-line row.
#
# The "vom" table header appears separated by double-newlines from the date value
# (unlike "Bearbeitung vom 08.10.2025" which uses spaces).  Requiring \n after
# "vom" disambiguates the two occurrences.
_VOM_DATE = re.compile(r"\bvom\n[\s\n]+(\d{2}\.\d{2}\.\d{4})")

# After pdfminer's extraction, the column headers appear left-to-right:
# "Rechnung\n\nSoz.Vers.\n\nVergütung\n\n<rechnung_amount>".
# The Rechnung (invoice) amount is the first number after the last column header.
_RECHNUNG_AMOUNT = re.compile(r"Verg[üu]tung[\s\n]+(\d{1,4}[.,]\d{2})")

# Auszahlungsbetrag total: last amount before the "Wir überweisen" paragraph.
# Using greedy .* to skip past all intermediate amounts.
_AUSZAHLUNG = re.compile(r"Auszahlungsbetrag:.*(\d{1,4}[.,]\d{2})\s*\n", re.DOTALL)

# Rejection indicators
_REJECTION_KEYWORDS = re.compile(
    r"\b(abgelehnt|keine\s+Verg[üu]tung|Ablehnung|nicht\s+erstattungsf[äa]hig)\b",
    re.IGNORECASE,
)

# Patient name: first non-empty line after the Geschäftsfall line
# (e.g. "Johanna Ladenhauf, 13.01.2022")
_PATIENT_LINE = re.compile(
    r"Gesch[äa]ftsfall[:\s]+\d+\s*\n\s*([^\n]+)",
    re.MULTILINE,
)


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class MerkurResult:
    geschaeftsfall_nr: Optional[str] = None
    document_date: Optional[datetime] = None
    patient_name: Optional[str] = None
    invoice_date: Optional[datetime] = None      # the "vom" column — matches Invoice.date
    invoice_amount: Optional[float] = None       # the "Rechnung" column
    reimbursed_amount: Optional[float] = None    # the "Auszahlungsbetrag" total
    result_state: MerkurResultState = MerkurResultState.UNKNOWN
    raw_text: str = field(default="", repr=False)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_merkur_result_pdf(file_path: str) -> MerkurResult:
    """Extract structured data from an Ambulante Abrechnungsinformation PDF."""
    text = _extract_text(file_path)
    result = MerkurResult(raw_text=text)

    result.geschaeftsfall_nr = _extract_geschaeftsfall(text)
    result.document_date = _extract_document_date(text)
    result.patient_name = _extract_patient_name(text)

    table = _extract_table_row(text)
    if table:
        result.invoice_date, result.invoice_amount = table

    result.reimbursed_amount = _extract_auszahlung(text)
    result.result_state = _determine_state(text, result.reimbursed_amount)

    return result


# ---------------------------------------------------------------------------
# Extraction helpers
# ---------------------------------------------------------------------------

def _extract_text(file_path: str) -> str:
    try:
        text = pdfminer_extract_text(file_path) or ""
        return text.strip()
    except Exception:
        return ""


def _extract_document_date(text: str) -> Optional[datetime]:
    for pat, fmt in [(_DOC_DATE_BEARBEITUNG, "de"), (_DOC_DATE_ISO, "iso"), (_DOC_DATE_DE, "de")]:
        m = pat.search(text)
        if m:
            try:
                g = m.groups()
                if fmt == "iso":
                    return datetime(int(g[0]), int(g[1]), int(g[2]))
                else:
                    return datetime(int(g[2]), int(g[1]), int(g[0]))
            except ValueError:
                continue
    return None


def _extract_geschaeftsfall(text: str) -> Optional[str]:
    m = _GESCHAEFTSFALL.search(text)
    return m.group(1) if m else None


def _extract_patient_name(text: str) -> Optional[str]:
    m = _PATIENT_LINE.search(text)
    if not m:
        return None
    raw = m.group(1).strip()
    # Strip trailing date like ", 13.01.2022"
    name = re.sub(r",\s*\d{2}\.\d{2}\.\d{4}\s*$", "", raw).strip()
    return name if name else None


def _extract_table_row(text: str) -> Optional[tuple[datetime, float]]:
    """Return (invoice_date, invoice_amount) from the PDF table.

    pdfminer extracts columns non-linearly, so each value is matched separately:
    - vom date: the date immediately following the "vom" column header (newline-separated)
    - invoice amount: the first number after the "Vergütung" column header (Rechnung value)
    """
    date_match = _VOM_DATE.search(text)
    amount_match = _RECHNUNG_AMOUNT.search(text)
    if not date_match or not amount_match:
        return None
    try:
        d, mo, y = date_match.group(1).split(".")
        inv_date = datetime(int(y), int(mo), int(d))
        inv_amount = float(amount_match.group(1).replace(",", "."))
        return inv_date, inv_amount
    except (ValueError, AttributeError):
        return None


def _extract_auszahlung(text: str) -> Optional[float]:
    m = _AUSZAHLUNG.search(text)
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", "."))
    except ValueError:
        return None


def _determine_state(text: str, reimbursed_amount: Optional[float]) -> MerkurResultState:
    if _REJECTION_KEYWORDS.search(text):
        return MerkurResultState.REJECTED
    if reimbursed_amount is not None:
        return MerkurResultState.REIMBURSED if reimbursed_amount > 0 else MerkurResultState.REJECTED
    return MerkurResultState.UNKNOWN
