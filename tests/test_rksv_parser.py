"""Unit tests for services/rksv_parser.parse_rksv — pure stdlib, no image I/O."""
import pytest
from datetime import datetime

from services.rksv_parser import parse_rksv


# A valid minimal RKSV string (prefix + 12 underscore-separated fields)
_VALID = "_R1-AT0_KASSE1_BELEG42_2024-03-15T14:30:00_12,50_5,00_0,00_0,00_3,50_CERT123_SIGPREV_SIG=="


def test_valid_payload():
    result = parse_rksv(_VALID)
    assert result is not None
    assert result.date == datetime(2024, 3, 15, 14, 30, 0)
    # total = abs(12.50) + abs(5.00) + abs(0.00) + abs(0.00) + abs(3.50)
    assert result.amount == pytest.approx(21.00, abs=0.001)
    assert result.kassen_id == "KASSE1"
    assert result.beleg_nr == "BELEG42"


def test_non_rksv_prefix_returns_none():
    assert parse_rksv("PLAIN_QR_DATA") is None
    assert parse_rksv("") is None


def test_too_few_parts_returns_none():
    # Only 8 underscore-separated parts (needs >= 10)
    short = "_R1-AT0_KASSE1_BELEG1_2024-01-01T00:00:00_1,00_2,00"
    assert parse_rksv(short) is None


def test_negative_amounts_summed_by_abs():
    # Negative amounts represent refunds — abs() is applied before summing
    qr = "_R1-AT0_K_B_2024-06-01T10:00:00_-10,00_5,00_0,00_0,00_0,00_C_P_S"
    result = parse_rksv(qr)
    assert result is not None
    assert result.amount == pytest.approx(15.00, abs=0.001)


def test_bad_date_returns_none():
    bad = "_R1-AT0_K_B_NOT-A-DATE_1,00_2,00_0,00_0,00_0,00_C_P_S"
    assert parse_rksv(bad) is None


def test_comma_decimal_separator():
    qr = "_R1-AT0_K_B_2025-12-31T23:59:59_99,99_0,00_0,00_0,00_0,00_C_P_S"
    result = parse_rksv(qr)
    assert result is not None
    assert result.amount == pytest.approx(99.99, abs=0.001)


def test_other_certificate_prefix_accepted():
    qr = "_R1-AT100_K_B_2024-06-01T10:00:00_1,00_0,00_0,00_0,00_0,00_C_P_S"
    result = parse_rksv(qr)
    assert result is not None
    assert result.amount == pytest.approx(1.00, abs=0.001)


def test_refund_flagged():
    qr = "_R1-AT0_K_B_2024-06-01T10:00:00_-10,00_0,00_0,00_0,00_0,00_C_P_S"
    result = parse_rksv(qr)
    assert result.is_refund is True
    assert result.amount == pytest.approx(10.00, abs=0.001)
    assert parse_rksv(_VALID).is_refund is False


def _write_qr(path, text):
    zxingcpp = pytest.importorskip("zxingcpp")
    from PIL import Image
    img = zxingcpp.write_barcode(zxingcpp.BarcodeFormat.QRCode, text, width=300, height=300)
    Image.fromarray(img).convert("RGB").save(path)


def test_image_roundtrip(tmp_path):
    from services.rksv_parser import extract_rksv_from_image
    f = tmp_path / "receipt.png"
    _write_qr(f, _VALID)
    result = extract_rksv_from_image(str(f))
    assert result is not None
    assert result.amount == pytest.approx(21.00, abs=0.001)


def test_pdf_upload_is_scanned(tmp_path):
    """A PDF upload must not crash the scan (it used to raise in Pillow)."""
    pytest.importorskip("pypdfium2")
    from PIL import Image
    from services.rksv_parser import extract_rksv_from_image
    png = tmp_path / "q.png"
    _write_qr(png, _VALID)
    from PIL import JpegImagePlugin  # noqa: F401  (registers JPEG for the PDF writer)
    pdf = tmp_path / "receipt.pdf"
    Image.open(png).save(pdf)
    result = extract_rksv_from_image(str(pdf))
    assert result is not None
