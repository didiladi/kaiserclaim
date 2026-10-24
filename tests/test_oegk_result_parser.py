"""Unit tests for services/oegk_result_parser — synthetic text, no real patient data."""
from datetime import date

from services.oegk_result_parser import parse_oegk_text

# Shaped like pdfminer's output for a real confirmation (double spaces and all).
_TEXT = """Frau Erika Muster

Bestätigung über die Kostenerstattung

Patient:

VSNR

1234 010190

Erika Muster BSc

Behandler(in): Dr. Max Beispiel

Für  Ihre  Aufwendungen  in  der  Höhe  von  1.350,00  Euro  für  Leistungen  vom  27.04.2026  bis 
28.04.2026 haben wir Ihnen 62,73 Euro erstattet. 
Die Überweisung erfolgte am 29.04.2026 auf nachstehende Bankverbindung:
IBAN: AT00 0000 0000 0000 0000
"""


def test_parses_all_fields():
    r = parse_oegk_text(_TEXT)
    assert r is not None
    assert r.patient_name == "Erika Muster BSc"
    assert r.patient_svnr == "1234010190"
    assert r.doctor_name == "Dr. Max Beispiel"
    assert r.invoice_amount == 1350.00
    assert r.reimbursed_amount == 62.73
    assert r.service_from == date(2026, 4, 27)
    assert r.service_to == date(2026, 4, 28)
    assert r.payout_date == date(2026, 4, 29)


def test_not_a_confirmation_returns_none():
    assert parse_oegk_text("Ein anderes Schreiben der ÖGK") is None
    assert parse_oegk_text("") is None


def test_missing_field_returns_none():
    assert parse_oegk_text(_TEXT.replace("Behandler(in): Dr. Max Beispiel", "")) is None


def test_dedupe_key_stable_and_distinct():
    a = parse_oegk_text(_TEXT)
    b = parse_oegk_text(_TEXT)
    c = parse_oegk_text(_TEXT.replace("62,73", "62,74"))
    assert a.dedupe_key == b.dedupe_key
    assert a.dedupe_key != c.dedupe_key


def test_result_does_not_leak_iban():
    r = parse_oegk_text(_TEXT)
    assert "AT00" not in repr(r)
