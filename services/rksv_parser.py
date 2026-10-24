"""
Austrian RKSV QR code parser.

Every Austrian cash register receipt must include a signed QR code in the
RKSV format (Registrierkassensicherheitsverordnung). The QR contains the
date, time, and all tax-category amounts — far more reliable than OCR+regex.

Format:
  _R1-AT0_{Kassen-ID}_{Beleg-Nr}_{Datum-Uhrzeit}_{Betrag-Normal}_{Betrag-Erm1}
           _{Betrag-Erm2}_{Betrag-Besonders}_{Betrag-Null}_{Zertifikat-SN}
           _{Sig-Vorwert}_{Signatur}

Amount fields use comma as decimal separator (Austrian locale).
Total = sum of abs values of all five Betrag fields; a negative sum flags a refund.
"""
import logging
import re
from datetime import datetime
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Optional

logger = logging.getLogger(__name__)

# R1-AT0 is the usual prefix; other certificate providers use R1-AT1, R1-AT100, ...
_RKSV_PREFIX = re.compile(r"^_R1-AT\d+_")


@dataclass
class RksvData:
    date: datetime
    amount: float
    kassen_id: str
    beleg_nr: str
    is_refund: bool = False


def _load_image_corrected(file_path: str):
    """Open image (or render page 1 of a PDF) with EXIF rotation applied."""
    from PIL import Image, ImageOps
    if Path(file_path).suffix.lower() == ".pdf":
        import pypdfium2 as pdfium
        pdf = pdfium.PdfDocument(file_path)
        try:
            return pdf[0].render(scale=3).to_pil().convert("RGB")
        finally:
            pdf.close()
    img = Image.open(file_path)
    img = ImageOps.exif_transpose(img)
    return img.convert("RGB")


def _scan_with_zxing(img) -> list[str]:
    """Try zxing-cpp, which handles phone photos better than pyzbar."""
    try:
        import zxingcpp
        import numpy as np
        results = zxingcpp.read_barcodes(np.array(img))
        return [r.text for r in results if r.valid]
    except Exception:
        logger.warning("zxing-cpp scan failed", exc_info=True)
        return []


def _scan_with_pyzbar(img) -> list[str]:
    """Fallback to pyzbar."""
    try:
        from pyzbar.pyzbar import decode, ZBarSymbol
        results = decode(img, symbols=[ZBarSymbol.QRCODE])
        return [r.data.decode("utf-8", errors="replace") for r in results]
    except Exception:
        logger.warning("pyzbar scan failed", exc_info=True)
        return []


def _candidate_images(img) -> Iterator:
    """Yield the image in progressively different shapes: thermal receipts and
    large phone photos each trip up scanners in different ways."""
    from PIL import Image, ImageEnhance, ImageFilter

    yield img
    w, h = img.size
    for max_side in (2000, 1200, 800):
        if max(w, h) > max_side:
            scale = max_side / max(w, h)
            yield img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)

    gray = img.convert("L")
    contrast = ImageEnhance.Contrast(gray).enhance(2.0)
    yield contrast
    yield contrast.filter(ImageFilter.SHARPEN)
    yield gray.point(lambda p: 255 if p > 128 else 0)
    for angle in (90, 180, 270):
        yield img.rotate(angle, expand=True)


def iter_qr_codes(file_path: str) -> Iterator[str]:
    """Lazily yield decoded QR texts, deduplicated, trying each candidate image."""
    img = _load_image_corrected(file_path)
    seen: set[str] = set()
    for candidate in _candidate_images(img):
        for text in _scan_with_zxing(candidate) or _scan_with_pyzbar(candidate):
            if text not in seen:
                seen.add(text)
                yield text


def extract_qr_codes(file_path: str) -> list[str]:
    """Return decoded text of every QR code found in an image or PDF."""
    return list(iter_qr_codes(file_path))


def parse_rksv(qr_text: str) -> Optional[RksvData]:
    """
    Parse a single QR string. Returns RksvData or None if it is not valid RKSV.
    """
    if not _RKSV_PREFIX.match(qr_text):
        return None

    parts = qr_text.split("_")
    # Index layout after splitting on "_":
    #   0  = ""  (leading underscore)
    #   1  = "R1-AT0"
    #   2  = Kassen-ID
    #   3  = Beleg-Nr
    #   4  = Datum-Uhrzeit  (ISO 8601: yyyy-MM-ddTHH:mm:ss)
    #   5  = Betrag-Normal  (20% VAT)
    #   6  = Betrag-Erm1    (10% VAT)
    #   7  = Betrag-Erm2    (13% VAT)
    #   8  = Betrag-Besonders
    #   9  = Betrag-Null    (0% VAT)
    #   10 = Zertifikat-Seriennummer
    #   11 = Sig-Vorwert
    #   12 = Signatur
    if len(parts) < 10:
        return None

    try:
        date = datetime.fromisoformat(parts[4])
        amounts = [float(p.replace(",", ".")) for p in parts[5:10]]
        total = round(sum(abs(a) for a in amounts), 2)
        return RksvData(
            date=date,
            amount=total,
            kassen_id=parts[2],
            beleg_nr=parts[3],
            is_refund=sum(amounts) < 0,
        )
    except (ValueError, IndexError):
        return None


def extract_rksv_from_image(file_path: str) -> Optional[RksvData]:
    """Return the first valid RKSV payload found; keeps scanning past non-RKSV QR codes."""
    try:
        for qr_text in iter_qr_codes(file_path):
            result = parse_rksv(qr_text)
            if result:
                return result
    except Exception:
        logger.warning("RKSV extraction failed for %s", Path(file_path).name, exc_info=True)
    return None
