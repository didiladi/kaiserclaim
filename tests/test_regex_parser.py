"""Unit tests for services/regex_parser.py — pure stdlib, no system deps."""
import pytest
from datetime import datetime

from services.regex_parser import parse_pharmacy_receipt, _extract_date, _extract_amount, _extract_atu


# ---------------------------------------------------------------------------
# Date extraction
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("text,expected", [
    ("Datum: 15.03.2024", datetime(2024, 3, 15)),
    ("15.03.24 Kassenbon", datetime(2024, 3, 15)),
    ("15/03/2024", datetime(2024, 3, 15)),
    ("2024-03-15", datetime(2024, 3, 15)),
    ("kein Datum hier", None),
    ("32.13.2024 ungültig", None),
])
def test_extract_date(text, expected):
    assert _extract_date(text) == expected


# ---------------------------------------------------------------------------
# Amount extraction
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("text,expected", [
    ("Betrag EUR 12,90", 12.90),
    ("Betrag: EUR 5.50", 5.50),
    ("Summe EUR 99,99", 99.99),
    ("Gesamt: EUR 7,00", 7.00),
    ("Total: € 3.14", 3.14),
    ("EUR: 18,90", 18.90),
    ("18,90 EUR", 18.90),
    ("zu 6,30", 6.30),
    ("kein Betrag", None),
    ("Betrag EUR 0,00", None),    # zero is rejected
])
def test_extract_amount(text, expected):
    result = _extract_amount(text)
    if expected is None:
        assert result is None
    else:
        assert result == pytest.approx(expected, abs=0.001)


# ---------------------------------------------------------------------------
# ATU extraction
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("text,expected", [
    ("ATU12345678 Apotheke", "ATU12345678"),
    ("atu 12345678", "ATU12345678"),
    ("kein ATU", None),
    ("ATU1234 zu kurz", None),
])
def test_extract_atu(text, expected):
    assert _extract_atu(text) == expected


# ---------------------------------------------------------------------------
# Full parse
# ---------------------------------------------------------------------------

def test_parse_pharmacy_receipt_full():
    text = "Datum: 10.01.2024\nBetrag EUR 24,50\nATU87654321"
    result = parse_pharmacy_receipt(text)
    assert result.date == datetime(2024, 1, 10)
    assert result.amount == pytest.approx(24.50, abs=0.001)
    assert result.atu_number == "ATU87654321"


def test_parse_pharmacy_receipt_empty():
    result = parse_pharmacy_receipt("")
    assert result.date is None
    assert result.amount is None
    assert result.atu_number is None
