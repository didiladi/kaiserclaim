"""
Celery task definitions.

All heavy I/O (OCR, browser automation) runs here, off the API event loop.
Each task updates the Invoice status atomically so the API always reflects
the true pipeline state.
"""
import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path

from celery import Celery
from celery.schedules import crontab

from core.config import get_settings
from core.database import AsyncSessionLocal
from models.domain import BenefitUsage, Invoice, InvoiceStatus, MerkurDocument, MerkurResultState, User
from sqlalchemy import select
from services.ocr_engine import pdf_to_text
from services.regex_parser import parse_pharmacy_receipt
from services.rksv_parser import extract_rksv_from_image
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
celery_app.conf.beat_schedule = {
    "merkur-inbox-daily": {
        "task": "workers.tasks.sync_merkur_inbox",
        "schedule": crontab(hour=7, minute=0),
        "kwargs": {"full_history": False},
    },
}


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


async def _finalize_invoice(invoice_id: str) -> None:
    """Write BenefitUsage (idempotent) and transition invoice to COMPLETED."""
    async with AsyncSessionLocal() as db:
        invoice = await db.get(Invoice, invoice_id)
        if not invoice:
            return

        if invoice.benefit_rule_id and invoice.amount is not None:
            existing = await db.execute(
                select(BenefitUsage).where(BenefitUsage.invoice_id == invoice.id)
            )
            if existing.scalar_one_or_none() is None:
                db.add(BenefitUsage(
                    invoice_id=invoice.id,
                    benefit_rule_id=invoice.benefit_rule_id,
                    amount_used=invoice.amount,
                ))

        invoice.status = InvoiceStatus.COMPLETED
        await db.commit()


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

        # Try fast RKSV QR extraction first (images only)
        from services.rksv_parser import extract_qr_codes
        qr_raw = extract_qr_codes(invoice.file_path)
        print(f"QR codes found: {qr_raw}", flush=True)
        rksv = extract_rksv_from_image(invoice.file_path)

        if rksv:
            date, amount = rksv.date, rksv.amount
            print(f"RKSV QR decoded: date={date} amount={amount}", flush=True)
        else:
            # Fall back to full OCR + regex
            text = _run(pdf_to_text(invoice.file_path))
            parsed = parse_pharmacy_receipt(text)
            date, amount = parsed.date, parsed.amount
            print(f"OCR fallback: date={date} amount={amount}", flush=True)

        async def _update():
            async with AsyncSessionLocal() as db:
                inv = await db.get(Invoice, invoice_id)
                if inv:
                    inv.amount = amount
                    inv.date = date
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

        if settings.merkur_dry_run:
            print(f"[DRY RUN] Skipping Merkur portal submission for invoice {invoice_id}", flush=True)
        else:
            bot = MerkurBot()
            date_str = invoice.date.strftime("%d.%m.%Y") if invoice.date else ""
            success = _run(bot.submit_pharmacy_receipt(
                invoice_pdf=invoice.file_path,
                amount=invoice.amount or 0.0,
                date=date_str,
                patient_name=invoice.patient_name or "",
            ))
            if not success:
                raise RuntimeError("Merkur submission did not return a success signal")

        _run(_set_status(invoice_id, InvoiceStatus.MERKUR_SUBMITTED))
        # Finalization (BenefitUsage + terminal status) now happens in sync_merkur_inbox
        # once Merkur places the result PDF in the Postfach.
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


@celery_app.task(bind=True, max_retries=3, default_retry_delay=300)
def sync_merkur_inbox(self, full_history: bool = False) -> dict:
    """Scrape Ambulante Abrechnungsinformation data from the Merkur Postfach SPA.

    Deduplicates by Geschäftsfall number and matches results back to
    MERKUR_SUBMITTED (or COMPLETED) invoices.  On a unique match the invoice
    is transitioned to MERKUR_REIMBURSED / MERKUR_REJECTED.
    """
    try:
        users = _run(_get_all_users())
        total_new = 0

        for user in users:
            output_dir = Path(settings.storage_root) / str(user.id) / "merkur_documents"
            output_dir.mkdir(parents=True, exist_ok=True)

            if settings.merkur_dry_run:
                print(f"[DRY RUN] Skipping Merkur inbox sync for user {user.id}", flush=True)
                continue

            bot = MerkurBot()
            docs = _run(bot.download_inbox_documents(str(output_dir), full_history=full_history))

            for doc_meta in docs:
                geschaeftsfall_nr = doc_meta.get("geschaeftsfall_nr")
                if not geschaeftsfall_nr:
                    print(f"[sync_merkur_inbox] No Geschäftsfall in scraped doc — skipping", flush=True)
                    continue

                # Dedup: skip if already stored
                if _run(_merkur_doc_exists(geschaeftsfall_nr)):
                    continue

                merkur_doc = _run(_create_merkur_document(user.id, doc_meta))
                total_new += 1

                invoice = _run(_find_matching_invoice(
                    user_id=user.id,
                    patient_name=doc_meta.get("patient_name"),
                    invoice_date=doc_meta.get("invoice_date"),
                    invoice_amount=doc_meta.get("invoice_amount"),
                ))

                if invoice:
                    _run(_link_and_finalize(merkur_doc.id, invoice, doc_meta["result_state"]))

        return {"synced": total_new, "full_history": full_history}

    except Exception as exc:
        raise self.retry(exc=exc)


async def _get_all_users() -> list[User]:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User))
        return list(result.scalars().all())


async def _merkur_doc_exists(geschaeftsfall_nr: str) -> bool:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(MerkurDocument).where(MerkurDocument.geschaeftsfall_nr == geschaeftsfall_nr)
        )
        return result.scalar_one_or_none() is not None


async def _create_merkur_document(user_id, doc_meta: dict) -> MerkurDocument:
    raw = doc_meta.get("raw_text") or ""
    doc = MerkurDocument(
        user_id=user_id,
        geschaeftsfall_nr=doc_meta["geschaeftsfall_nr"],
        title=doc_meta.get("title", "Ambulante Abrechnungsinformation VN"),
        document_date=doc_meta.get("document_date"),
        file_path=doc_meta.get("pdf_path"),
        patient_name=doc_meta.get("patient_name"),
        invoice_amount=doc_meta.get("invoice_amount"),
        reimbursed_amount=doc_meta.get("reimbursed_amount"),
        result_state=doc_meta["result_state"],
        raw_text=raw[:10_000] if raw else None,
    )
    async with AsyncSessionLocal() as db:
        db.add(doc)
        await db.commit()
        await db.refresh(doc)
    return doc


async def _find_matching_invoice(
    user_id,
    patient_name: str | None,
    invoice_date,
    invoice_amount: float | None,
) -> Invoice | None:
    """Find an invoice in MERKUR_SUBMITTED or COMPLETED matching patient + date + amount."""
    if not invoice_date or invoice_amount is None:
        return None

    async with AsyncSessionLocal() as db:
        stmt = select(Invoice).where(
            Invoice.user_id == user_id,
            Invoice.status.in_([InvoiceStatus.MERKUR_SUBMITTED, InvoiceStatus.COMPLETED]),
            Invoice.date.isnot(None),
            Invoice.amount.isnot(None),
        )
        result = await db.execute(stmt)
        candidates = result.scalars().all()

    matches = []
    for inv in candidates:
        # Date match: same calendar day
        if inv.date and abs((inv.date.date() - invoice_date.date()).days) > 0:
            continue
        # Amount match: within 1 cent tolerance for float comparison
        if inv.amount is not None and abs(inv.amount - invoice_amount) > 0.01:
            continue
        # Patient name match (case-insensitive, if we have both)
        if patient_name and inv.patient_name:
            if patient_name.lower() not in inv.patient_name.lower() and \
               inv.patient_name.lower() not in patient_name.lower():
                continue
        matches.append(inv)

    return matches[0] if len(matches) == 1 else None


async def _link_and_finalize(merkur_doc_id, invoice: Invoice, result_state: MerkurResultState) -> None:
    async with AsyncSessionLocal() as db:
        doc = await db.get(MerkurDocument, merkur_doc_id)
        inv = await db.get(Invoice, invoice.id)
        if not doc or not inv:
            return

        doc.invoice_id = inv.id

        # Only transition invoices that are still waiting for a result
        if inv.status == InvoiceStatus.MERKUR_SUBMITTED:
            if result_state == MerkurResultState.REIMBURSED:
                inv.status = InvoiceStatus.MERKUR_REIMBURSED
                # Write BenefitUsage with actual reimbursed amount
                if inv.benefit_rule_id:
                    existing = await db.execute(
                        select(BenefitUsage).where(BenefitUsage.invoice_id == inv.id)
                    )
                    if existing.scalar_one_or_none() is None:
                        db.add(BenefitUsage(
                            invoice_id=inv.id,
                            benefit_rule_id=inv.benefit_rule_id,
                            amount_used=doc.reimbursed_amount or inv.amount or 0.0,
                        ))
            elif result_state == MerkurResultState.REJECTED:
                inv.status = InvoiceStatus.MERKUR_REJECTED
            # UNKNOWN: leave in MERKUR_SUBMITTED

        await db.commit()


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
