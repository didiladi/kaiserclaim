"""
Celery task definitions.

All heavy I/O (OCR, browser automation) runs here, off the API event loop.
Each task updates the Invoice status atomically so the API always reflects
the true pipeline state.
"""
import asyncio
from datetime import datetime
from pathlib import Path

from celery import Celery

from core.config import get_settings
from core.database import AsyncSessionLocal
from models.domain import Invoice, InvoiceStatus
from services.ocr_engine import pdf_to_text
from services.regex_parser import parse_pharmacy_receipt
from workers.playwright_bot import MerkurBot, OegkBot

settings = get_settings()

celery_app = Celery(
    "kaiserclaim",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Europe/Vienna",
    enable_utc=True,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


async def _set_status(invoice_id: str, status: InvoiceStatus) -> None:
    async with AsyncSessionLocal() as db:
        invoice = await db.get(Invoice, invoice_id)
        if invoice:
            invoice.status = status
            await db.commit()


async def _get_invoice(invoice_id: str) -> Invoice | None:
    async with AsyncSessionLocal() as db:
        return await db.get(Invoice, invoice_id)


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------

@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def run_ocr(self, invoice_id: str) -> dict:
    """OCR the invoice file and update metadata. MVP: pharmacy short-track."""
    try:
        _run(_set_status(invoice_id, InvoiceStatus.OCR_PROCESSING))

        invoice = _run(_get_invoice(invoice_id))
        if not invoice:
            raise ValueError(f"Invoice {invoice_id} not found")

        text = _run(pdf_to_text(invoice.file_path))
        parsed = parse_pharmacy_receipt(text)

        async def _update():
            async with AsyncSessionLocal() as db:
                inv = await db.get(Invoice, invoice_id)
                if inv:
                    inv.amount = parsed.amount
                    inv.date = parsed.date
                    # Pharmacy receipts skip ÖGK — go straight to Merkur
                    inv.status = InvoiceStatus.READY_FOR_MERKUR
                    await db.commit()

        _run(_update())
        return {"invoice_id": invoice_id, "status": "READY_FOR_MERKUR"}

    except Exception as exc:
        raise self.retry(exc=exc)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=120)
def submit_to_merkur(self, invoice_id: str) -> dict:
    """Submit invoice PDF to Merkur portal via headless Playwright."""
    try:
        invoice = _run(_get_invoice(invoice_id))
        if not invoice:
            raise ValueError(f"Invoice {invoice_id} not found")

        bot = MerkurBot()
        date_str = invoice.date.strftime("%d.%m.%Y") if invoice.date else ""
        success = _run(bot.submit_pharmacy_receipt(
            invoice_pdf=invoice.file_path,
            amount=invoice.amount or 0.0,
            date=date_str,
        ))

        if not success:
            raise RuntimeError("Merkur submission did not return a success signal")

        _run(_set_status(invoice_id, InvoiceStatus.MERKUR_SUBMITTED))
        return {"invoice_id": invoice_id, "status": "MERKUR_SUBMITTED"}

    except Exception as exc:
        raise self.retry(exc=exc)


@celery_app.task(bind=True, max_retries=5, default_retry_delay=300)
def submit_to_oegk(self, invoice_id: str) -> dict:
    """Submit invoice to ÖGK (persistent context, user handles 2FA)."""
    try:
        invoice = _run(_get_invoice(invoice_id))
        if not invoice:
            raise ValueError(f"Invoice {invoice_id} not found")

        bot = OegkBot()
        date_str = invoice.date.strftime("%d.%m.%Y") if invoice.date else ""
        success = _run(bot.submit_invoice(
            invoice_pdf=invoice.file_path,
            amount=invoice.amount or 0.0,
            date=date_str,
        ))

        if not success:
            raise RuntimeError("ÖGK submission did not return a success signal")

        _run(_set_status(invoice_id, InvoiceStatus.OEGK_SUBMITTED))
        return {"invoice_id": invoice_id, "status": "OEGK_SUBMITTED"}

    except Exception as exc:
        raise self.retry(exc=exc)


@celery_app.task(bind=True, max_retries=10, default_retry_delay=600)
def poll_oegk_refund(self, invoice_id: str, output_dir: str) -> dict:
    """Poll ÖGK portal for refund PDF; retries up to ~100 min (10 × 10 min)."""
    try:
        bot = OegkBot()
        refund_path = _run(bot.download_refund_pdf(output_dir))

        if not refund_path:
            raise self.retry(exc=RuntimeError("Refund PDF not yet available"))

        async def _mark_refunded():
            async with AsyncSessionLocal() as db:
                inv = await db.get(Invoice, invoice_id)
                if inv:
                    inv.status = InvoiceStatus.OEGK_REFUNDED
                    await db.commit()

        _run(_mark_refunded())
        return {"invoice_id": invoice_id, "refund_pdf": refund_path, "status": "OEGK_REFUNDED"}

    except Exception as exc:
        raise self.retry(exc=exc)
