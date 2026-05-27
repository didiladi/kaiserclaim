"""
Unit tests for services/merkur_result_parser.py.

The sample PDF: /home/didi/Downloads/Ambulante Abrechnungsinformation VN von 08-10-2025.pdf
Expected data from the PDF:
  - Geschäftsfall: 202501798104
  - Bearbeitung vom: 08.10.2025
  - Patient: Johanna Ladenhauf (DOB 13.01.2022)
  - vom (receipt date): 07.10.2024
  - Rechnung (invoice amount): 12,00 → 12.0
  - Vergütung / Auszahlungsbetrag: 9,60 → 9.6
  - Result state: REIMBURSED
"""
from datetime import datetime
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

SAMPLE_PDF = Path("/home/didi/Downloads/Ambulante Abrechnungsinformation VN von 08-10-2025.pdf")


@pytest.mark.skipif(not SAMPLE_PDF.exists(), reason="Sample PDF not available in this environment")
def test_parse_sample_pdf():
    from services.merkur_result_parser import parse_merkur_result_pdf, MerkurResult
    from models.domain import MerkurResultState

    result = parse_merkur_result_pdf(str(SAMPLE_PDF))

    assert result.geschaeftsfall_nr == "202501798104"
    assert result.document_date == datetime(2025, 10, 8)
    assert result.patient_name is not None
    assert "Johanna" in result.patient_name or "Ladenhauf" in result.patient_name
    assert result.invoice_date == datetime(2024, 10, 7)
    assert result.invoice_amount == pytest.approx(12.0, abs=0.01)
    assert result.reimbursed_amount == pytest.approx(9.6, abs=0.01)
    assert result.result_state == MerkurResultState.REIMBURSED
    assert result.raw_text  # non-empty


def test_determine_state_reimbursed():
    from services.merkur_result_parser import _determine_state
    from models.domain import MerkurResultState

    assert _determine_state("normal text", 9.60) == MerkurResultState.REIMBURSED


def test_determine_state_zero_is_rejected():
    from services.merkur_result_parser import _determine_state
    from models.domain import MerkurResultState

    assert _determine_state("normal text", 0.0) == MerkurResultState.REJECTED


def test_determine_state_keyword_rejected():
    from services.merkur_result_parser import _determine_state
    from models.domain import MerkurResultState

    assert _determine_state("Leider abgelehnt worden.", None) == MerkurResultState.REJECTED
    assert _determine_state("keine Vergütung vorgesehen.", None) == MerkurResultState.REJECTED


def test_determine_state_unknown():
    from services.merkur_result_parser import _determine_state
    from models.domain import MerkurResultState

    assert _determine_state("no useful info", None) == MerkurResultState.UNKNOWN


def test_extract_geschaeftsfall():
    from services.merkur_result_parser import _extract_geschaeftsfall

    text = "Geschäftsfall: 202501798104\nJohanna Ladenhauf"
    assert _extract_geschaeftsfall(text) == "202501798104"

    # ASCII fallback (ä → a)
    text2 = "Geschaftsfall: 12345"
    assert _extract_geschaeftsfall(text2) == "12345"


def test_extract_auszahlung():
    from services.merkur_result_parser import _extract_auszahlung

    # Mirrors actual pdfminer layout where Auszahlungsbetrag amount is last before newline
    text = "Auszahlungsbetrag:\n\nVergütung\n\n12,00\n\nEuro\n\n9,60\n\n9,60\n"
    assert _extract_auszahlung(text) == pytest.approx(9.60, abs=0.001)

    assert _extract_auszahlung("no amount here") is None


def test_extract_table_row():
    from services.merkur_result_parser import _extract_table_row

    # Mirrors the actual pdfminer multi-column extraction order
    text = "MHNG1E24S1\n\nArzneimittel\n\nAuszahlungsbetrag:\n\nvom\n\n07.10.2024\n\nRechnung\n\nSoz.Vers.\n\nVergütung\n\n12,00\n\nEuro\n\n9,60\n\n9,60\n\nWir überweisen"
    result = _extract_table_row(text)
    assert result is not None
    inv_date, inv_amount = result
    assert inv_date == datetime(2024, 10, 7)
    assert inv_amount == pytest.approx(12.0, abs=0.01)


def test_extract_document_date_iso():
    from services.merkur_result_parser import _extract_document_date

    text = "Graz, 2025-10-08"
    assert _extract_document_date(text) == datetime(2025, 10, 8)


def test_extract_document_date_bearbeitung():
    from services.merkur_result_parser import _extract_document_date

    text = "Bearbeitung vom 08.10.2025"
    assert _extract_document_date(text) == datetime(2025, 10, 8)
