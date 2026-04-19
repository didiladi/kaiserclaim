"""
Regex-based metadata extraction for Austrian pharmacy receipts.

Austrian pharmacy receipts contain:
- A date (various formats)
- A total amount (€ or EUR)
- An ATU number (Umsatzsteuer-Identifikationsnummer, format: ATU + 8 digits)
"""
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


_DATE_PATTERNS = [
    r"\b(\d{2})\.(\d{2})\.(\d{4})\b",   # 15.03.2024
    r"\b(\d{2})/(\d{2})/(\d{4})\b",     # 15/03/2024
    r"\b(\d{4})-(\d{2})-(\d{2})\b",     # 2024-03-15
]

_AMOUNT_PATTERN = re.compile(
    r"(?:Gesamt|Total|Summe|Betrag|EUR|€)\s*[:\s]?\s*(\d{1,4}[.,]\d{2})",
    re.IGNORECASE,
)

_ATU_PATTERN = re.compile(r"\bATU\d{8}\b", re.IGNORECASE)


@dataclass
class PharmacyReceiptData:
    date: Optional[datetime]
    amount: Optional[float]
    atu_number: Optional[str]


def parse_pharmacy_receipt(text: str) -> PharmacyReceiptData:
    return PharmacyReceiptData(
        date=_extract_date(text),
        amount=_extract_amount(text),
        atu_number=_extract_atu(text),
    )


def _extract_date(text: str) -> Optional[datetime]:
    for pattern in _DATE_PATTERNS:
        match = re.search(pattern, text)
        if match:
            groups = match.groups()
            try:
                if len(groups[0]) == 4:
                    # YYYY-MM-DD
                    return datetime(int(groups[0]), int(groups[1]), int(groups[2]))
                else:
                    # DD.MM.YYYY or DD/MM/YYYY
                    return datetime(int(groups[2]), int(groups[1]), int(groups[0]))
            except ValueError:
                continue
    return None


def _extract_amount(text: str) -> Optional[float]:
    match = _AMOUNT_PATTERN.search(text)
    if not match:
        return None
    raw = match.group(1).replace(",", ".")
    try:
        return float(raw)
    except ValueError:
        return None


def _extract_atu(text: str) -> Optional[str]:
    match = _ATU_PATTERN.search(text)
    return match.group(0).upper() if match else None
