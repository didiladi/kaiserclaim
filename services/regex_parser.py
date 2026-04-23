"""
Regex-based metadata extraction for Austrian pharmacy receipts.
"""
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


_DATE_PATTERNS = [
    r"\b(\d{2})\.(\d{2})\.(\d{4})\b",   # 15.03.2024
    r"\b(\d{2})\.(\d{2})\.(\d{2})\b",   # 15.03.24
    r"\b(\d{2})/(\d{2})/(\d{4})\b",     # 15/03/2024
    r"\b(\d{4})-(\d{2})-(\d{2})\b",     # 2024-03-15
]

# Ordered from most specific to least specific.
# Each pattern must have exactly one capturing group for the numeric amount.
_AMOUNT_PATTERNS = [
    # "Betrag EUR" / "Betrag: EUR" followed by amount on same or next line
    re.compile(r"Betrag\s*:?\s*EUR\s*[\n\r\s]*(\d{1,4}[.,]\d{2})", re.IGNORECASE),
    # "Summe EUR" / "Gesamt EUR" etc. on same or next line
    re.compile(r"(?:Summe|Gesamt|Total)\s*:?\s*(?:EUR|€)?\s*[\n\r\s]*(\d{1,4}[.,]\d{2})", re.IGNORECASE),
    # Amount on same line as EUR/€ keyword
    re.compile(r"(?:EUR|€)\s*:?\s*(\d{1,4}[.,]\d{2})", re.IGNORECASE),
    re.compile(r"(\d{1,4}[.,]\d{2})\s*(?:EUR|€)", re.IGNORECASE),
    # "zu 18,90" — Austrian style item price (last resort, may be per-item not total)
    re.compile(r"\bzu\s+(\d{1,4}[.,]\d{2})", re.IGNORECASE),
]

_ATU_PATTERN = re.compile(r"\bATU\s*\d{8}\b", re.IGNORECASE)


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
                    return datetime(int(groups[0]), int(groups[1]), int(groups[2]))
                else:
                    year = int(groups[2])
                    if year < 100:
                        year += 2000
                    return datetime(year, int(groups[1]), int(groups[0]))
            except ValueError:
                continue
    return None


def _extract_amount(text: str) -> Optional[float]:
    for pattern in _AMOUNT_PATTERNS:
        match = pattern.search(text)
        if match:
            raw = match.group(1).replace(",", ".")
            try:
                value = float(raw)
                if value > 0:
                    return value
            except ValueError:
                continue
    return None


def _extract_atu(text: str) -> Optional[str]:
    match = _ATU_PATTERN.search(text)
    if not match:
        return None
    return re.sub(r"\s+", "", match.group(0)).upper()
