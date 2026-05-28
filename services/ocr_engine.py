import asyncio
import tempfile
from pathlib import Path

import ocrmypdf


async def pdf_to_text(file_path: str) -> str:
    """Run OCR on a PDF or image and return extracted plain text."""
    src = Path(file_path)
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        out_path = Path(tmp.name)

    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _run_ocr, src, out_path)

    text = await loop.run_in_executor(None, _extract_text, out_path)
    out_path.unlink(missing_ok=True)
    return text


async def pdf_to_text_native(file_path: str, ocr_fallback: bool = True) -> str:
    """
    Extract text from a PDF using pdfminer directly (no OCR, instant for digital PDFs).
    Falls back to full OCR only if the extracted text is too short (scanned document).
    """
    loop = asyncio.get_event_loop()
    text = await loop.run_in_executor(None, _extract_text, Path(file_path))

    # If the PDF already has meaningful text, return it directly
    if len(text.strip()) > 200:
        return text

    # Scanned document — fall back to OCR
    if ocr_fallback:
        return await pdf_to_text(file_path)
    return text


def _run_ocr(src: Path, dest: Path) -> None:
    ocrmypdf.ocr(
        src,
        dest,
        language="deu",
        deskew=True,
        force_ocr=True,
        progress_bar=False,
        image_dpi=300,  # phone photos report 72 DPI in EXIF but are much denser
    )


def _extract_text(pdf_path: Path) -> str:
    from pdfminer.high_level import extract_text

    return extract_text(str(pdf_path))
