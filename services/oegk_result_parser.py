"""
Parser for ÖGK 'Bestätigung über die Kostenerstattung' PDFs.

meine ÖGK offers this PDF for every refunded claim. It carries no case number,
but names patient, doctor, service dates, invoice amount and refund, which is
enough to match it back to an invoice. Only the fields we need are kept: the
PDF also holds an address and IBAN that must never be stored or logged.
"""
import hashlib
import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import BinaryIO, Optional

from pdfminer.high_level import extract_text as pdfminer_extract_text

_AMOUNT = r"(\d{1,3}(?:\.\d{3})*,\d{2}|\d+,\d{2})"
_DATE = r"(\d{2}\.\d{2}\.\d{4})"

_HEADER = re.compile(r"Bestätigung über die Kostenerstattung")
_PATIENT = re.compile(r"Patient:\s*VSNR\s*(\d{4} ?\d{6})\s*([^\n]+)")
_DOCTOR = re.compile(r"Behandler\(in\):\s*([^\n]+)")
_INVOICE_AMOUNT = re.compile(r"in der Höhe von " + _AMOUNT + r" Euro")
_SERVICE_RANGE = re.compile(r"Leistungen vom " + _DATE + r"\s+bis\s+" + _DATE)
_REFUND = re.compile(r"haben wir Ihnen " + _AMOUNT + r" Euro erstattet")
_PAYOUT_DATE = re.compile(r"Überweisung erfolgte am " + _DATE)


@dataclass
class OegkResult:
    patient_name: str
    patient_svnr: str
    doctor_name: str
    invoice_amount: float
    reimbursed_amount: float
    service_from: date
    service_to: date
    payout_date: date

    @property
    def dedupe_key(self) -> str:
        """Stable identity of a result: the PDF carries no case number."""
        parts = (
            self.patient_svnr, self.doctor_name, self.service_from.isoformat(),
            self.service_to.isoformat(), f"{self.invoice_amount:.2f}",
            f"{self.reimbursed_amount:.2f}", self.payout_date.isoformat(),
        )
        return hashlib.sha256("|".join(parts).encode()).hexdigest()


def _amount(text: str) -> float:
    return float(text.replace(".", "").replace(",", "."))


def _date(text: str) -> date:
    return datetime.strptime(text, "%d.%m.%Y").date()


def parse_oegk_text(text: str) -> Optional[OegkResult]:
    """Return the result, or None if the text is not a refund confirmation."""
    text = re.sub(r"[ \t ]+", " ", text)
    if not _HEADER.search(text):
        return None

    patient = _PATIENT.search(text)
    doctor = _DOCTOR.search(text)
    invoice = _INVOICE_AMOUNT.search(text)
    service = _SERVICE_RANGE.search(text)
    refund = _REFUND.search(text)
    payout = _PAYOUT_DATE.search(text)
    if not all((patient, doctor, invoice, service, refund, payout)):
        return None

    try:
        return OegkResult(
            patient_name=patient.group(2).strip(),
            patient_svnr=patient.group(1).replace(" ", ""),
            doctor_name=doctor.group(1).strip(),
            invoice_amount=_amount(invoice.group(1)),
            reimbursed_amount=_amount(refund.group(1)),
            service_from=_date(service.group(1)),
            service_to=_date(service.group(2)),
            payout_date=_date(payout.group(1)),
        )
    except ValueError:
        return None


def parse_oegk_pdf(source: str | BinaryIO) -> Optional[OegkResult]:
    """Parse a PDF given as a path or an open binary file. None if it is not a refund confirmation."""
    try:
        text = pdfminer_extract_text(source)
    except Exception:  # not a readable PDF; never log the content
        return None
    return parse_oegk_text(text)
