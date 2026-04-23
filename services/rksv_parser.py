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
Total = sum of abs values of all five Betrag fields (negatives = refunds).
"""
from datetime import datetime
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class RksvData:
    date: datetime
    amount: float
    kassen_id: str
    beleg_nr: str


def _load_image_corrected(file_path: str):
    """Open image and apply EXIF rotation so pixels match visual orientation."""
    from PIL import Image, ImageOps
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
        return []


def _scan_with_pyzbar(img) -> list[str]:
    """Fallback to pyzbar."""
    try:
        from pyzbar.pyzbar import decode, ZBarSymbol
        results = decode(img, symbols=[ZBarSymbol.QRCODE])
        return [r.data.decode("utf-8", errors="replace") for r in results]
    except Exception:
        return []


def extract_qr_codes(file_path: str) -> list[str]:
    """Return decoded text of every QR code found in an image file."""
    from PIL import Image, ImageEnhance

    img = _load_image_corrected(file_path)

    # Build candidate images: original + progressively smaller versions
    # (large phone photos overwhelm QR scanners)
    candidates = [img]
    w, h = img.size
    for max_side in (2000, 1200, 800):
        if max(w, h) > max_side:
            scale = max_side / max(w, h)
            candidates.append(img.resize((int(w * scale), int(h * scale)), Image.LANCZOS))

    # Also try high-contrast grayscale
    gray = img.convert("L")
    candidates.append(ImageEnhance.Contrast(gray).enhance(2.0))

    seen: set[str] = set()
    results: list[str] = []

    for candidate in candidates:
        found = _scan_with_zxing(candidate) or _scan_with_pyzbar(candidate)
        for text in found:
            if text not in seen:
                seen.add(text)
                results.append(text)
        if results:
            break

    return results


def parse_rksv(qr_text: str) -> Optional[RksvData]:
    """
    Parse a single QR string. Returns RksvData or None if it is not valid RKSV.
    """
    if not qr_text.startswith("_R1-AT0_"):
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
        )
    except (ValueError, IndexError):
        return None


def extract_rksv_from_image(file_path: str) -> Optional[RksvData]:
    """Scan all QR codes in an image and return the first valid RKSV payload."""
    try:
        for qr_text in extract_qr_codes(file_path):
            result = parse_rksv(qr_text)
            if result:
                return result
    except Exception:
        pass
    return None
