"""
Parser for Merkur 'Meine Einreichungen' summary SPA page text.

The summary page at portal.merkur.at/kporclient/einreichungen?gevoid=... shows
one or more Einreichung entries in Angular Material expansion panels.  This
module parses the innerText of each panel into structured data — no PDF needed.

Public API:
    parse_einreichung_text(text: str) -> EinreichungData | None
"""
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from models.domain import MerkurResultState

# ---------------------------------------------------------------------------
# Regex patterns (compiled once)
# ---------------------------------------------------------------------------

_DATE = re.compile(r'\b(\d{2})\.(\d{2})\.(\d{4})\b')
_GESCHAEFTSFALL = re.compile(r'Gesch[äa]ftsfallnummer:\s*(\d+)')
_BEARBEITET = re.compile(r'Bearbeitet\s+am\s+(\d{2}\.\d{2}\.\d{4})')
_ANWEISUNGSBETRAG = re.compile(r'Anweisungsbetrag:\s*€\s*([\d,.]+)')
_BEHANDLUNGSDATUM = re.compile(r'Behandlungsdatum:\s*(\d{2}\.\d{2}\.\d{4})')
_VERSICHERTE_PERSON = re.compile(r'Versicherte\s+Person:\s*([^\n]+)')
_GEFORDERT = re.compile(r'Gefordert:\s*€\s*([\d,.]+)')
_ABGELEHNT = re.compile(r'\b(Ablehnung|abgelehnt|nicht\s+erstattungsf[äa]hig)\b', re.IGNORECASE)
_ABGESCHLOSSEN = re.compile(r'\bAbgeschlossen\b')

# Academic title prefixes common in Austria
_TITLE_PREFIX = re.compile(
    r'^(Dipl\.?\s*-?\s*Ing\.?|Dr\.?|Prof\.?|Mag\.?|BSc\.?|MSc\.?|MBA\.?|'
    r'DI\.?|Ing\.?|MMag\.?|MR\.?|HR\.?|ao\.?\s*Univ\.?|Univ\.?-?Prof\.?)\s+',
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Public data class
# ---------------------------------------------------------------------------

@dataclass
class EinreichungData:
    geschaeftsfall_nr: str
    document_date: Optional[datetime]
    patient_name: Optional[str]
    invoice_date: Optional[datetime]
    invoice_amount: Optional[float]
    reimbursed_amount: Optional[float]
    result_state: MerkurResultState
    raw_text: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_amount(value: str) -> float:
    return float(value.replace('.', '').replace(',', '.'))


def _parse_date_str(s: str) -> Optional[datetime]:
    m = _DATE.search(s)
    if not m:
        return None
    try:
        return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    except ValueError:
        return None


def _strip_person(raw: str) -> str:
    """'Dipl.Ing. Dieter Ladenhauf, 17.02.1987' → 'Dieter Ladenhauf'"""
    # Drop DOB suffix (everything from first comma onward)
    name = raw.split(',')[0].strip()
    # Strip academic title prefixes iteratively
    prev = None
    while prev != name:
        prev = name
        name = _TITLE_PREFIX.sub('', name).strip()
    return name


# ---------------------------------------------------------------------------
# Public parser
# ---------------------------------------------------------------------------

def parse_einreichung_text(text: str) -> Optional[EinreichungData]:
    """Parse the innerText of one Einreichung panel from 'Meine Einreichungen'.

    Returns None if the panel doesn't contain a Geschäftsfallnummer (e.g. a
    collapsed panel that hasn't been expanded yet).
    """
    m = _GESCHAEFTSFALL.search(text)
    if not m:
        return None
    geschaeftsfall_nr = m.group(1)

    m = _BEARBEITET.search(text)
    document_date = _parse_date_str(m.group(1)) if m else None

    m = _ANWEISUNGSBETRAG.search(text)
    reimbursed_amount = _parse_amount(m.group(1)) if m else None

    m = _BEHANDLUNGSDATUM.search(text)
    invoice_date = _parse_date_str(m.group(1)) if m else None

    m = _VERSICHERTE_PERSON.search(text)
    patient_name = _strip_person(m.group(1).strip()) if m else None

    gefordert_values = [_parse_amount(v) for v in _GEFORDERT.findall(text)]
    invoice_amount = sum(gefordert_values) if gefordert_values else None

    has_rejection = bool(_ABGELEHNT.search(text))
    has_success = bool(_ABGESCHLOSSEN.search(text))
    if reimbursed_amount and reimbursed_amount > 0:
        result_state = MerkurResultState.REIMBURSED
    elif has_rejection and not has_success:
        result_state = MerkurResultState.REJECTED
    elif has_success:
        result_state = MerkurResultState.REIMBURSED
    else:
        result_state = MerkurResultState.UNKNOWN

    return EinreichungData(
        geschaeftsfall_nr=geschaeftsfall_nr,
        document_date=document_date,
        patient_name=patient_name,
        invoice_date=invoice_date,
        invoice_amount=invoice_amount,
        reimbursed_amount=reimbursed_amount,
        result_state=result_state,
        raw_text=text,
    )
