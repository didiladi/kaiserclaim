"""
Celery task definitions.

All heavy I/O (OCR, browser automation) runs here, off the API event loop.
Each task updates the Invoice status atomically so the API always reflects
the true pipeline state.
"""
import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from celery import Celery
from celery.exceptions import MaxRetriesExceededError
from celery.schedules import crontab

from core.config import get_settings
from core.database import AsyncSessionLocal
from models.domain import BenefitKind, BenefitRule, BenefitUsage, InsuredPerson, Invoice, InvoiceStatus, MerkurDocument, MerkurResultState, ResetPeriod, Tariff, User
from sqlalchemy import func, select, update
from schemas.payload import first_submission_status
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
# ÖGK tasks drive a headed browser (ID-Austria 2FA), so they are consumed only
# by a worker started with `-Q oegk` on a machine with a display. The cluster
# worker listens on the default queue and never picks them up.
OEGK_QUEUE = "oegk"
celery_app.conf.task_routes = {
    "workers.tasks.submit_to_oegk": {"queue": OEGK_QUEUE},
    "workers.tasks.poll_oegk_refund": {"queue": OEGK_QUEUE},
}
celery_app.conf.beat_schedule = {
    "merkur-inbox-daily": {
        "task": "workers.tasks.sync_merkur_inbox",
        "schedule": crontab(hour=7, minute=0),
        "kwargs": {"full_history": False},
    },
    "scan-unused-benefits-daily": {
        "task": "workers.tasks.scan_unused_benefits",
        "schedule": crontab(hour=8, minute=0),
    },
    "oegk-refund-poll-daily": {
        "task": "workers.tasks.poll_oegk_refunds",
        "schedule": crontab(hour=9, minute=0),
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


_VIENNA = ZoneInfo("Europe/Vienna")


def _portal_date(dt: datetime | None) -> str:
    """DD.MM.YYYY as the portals expect it, in Vienna local time.

    Invoice.date is timestamptz and comes back in UTC, so a receipt stamped
    00:30 Vienna time would otherwise be submitted as the previous day.
    """
    if dt is None:
        return ""
    if dt.tzinfo is not None:
        dt = dt.astimezone(_VIENNA)
    return dt.strftime("%d.%m.%Y")


def _ensure_local_file(invoice: Invoice) -> str:
    """Return a local path for the invoice file, fetching it from the API if needed.

    Uploads live on the cluster volume; the desktop ÖGK worker does not see it.
    """
    local = Path(invoice.file_path)
    if local.exists():
        return str(local)
    if not settings.api_base_url:
        raise FileNotFoundError(
            f"{invoice.file_path} not found locally and API_BASE_URL is not set"
        )
    import urllib.request

    dest = Path(settings.storage_root) / str(invoice.user_id) / local.name
    dest.parent.mkdir(parents=True, exist_ok=True)
    url = f"{settings.api_base_url.rstrip('/')}/api/v1/invoices/{invoice.id}/file?user_id={invoice.user_id}"
    with urllib.request.urlopen(url, timeout=60) as resp, dest.open("wb") as out:
        out.write(resp.read())
    return str(dest)


async def _get_invoice(invoice_id: str) -> Invoice | None:
    async with AsyncSessionLocal() as db:
        return await db.get(Invoice, invoice_id)


async def _try_transition(invoice_id: str, expected: InvoiceStatus, new: InvoiceStatus) -> bool:
    """Atomically move an invoice from `expected` to `new`.

    Returns False without changing anything if the invoice was not in `expected`
    (e.g. a retry running after an earlier attempt already claimed it). This is
    the guard that keeps a Celery retry from re-clicking a portal submission
    that may have already gone through.
    """
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            update(Invoice)
            .where(Invoice.id == invoice_id, Invoice.status == expected)
            .values(status=new)
            .returning(Invoice.id)
        )
        row = result.first()
        await db.commit()
        return row is not None


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

        # Missing date or amount means we can't safely advance the invoice —
        # route it to a human instead of silently submitting a 0.00 claim.
        next_status = (
            InvoiceStatus.NEEDS_REVIEW
            if date is None or amount is None
            else first_submission_status(invoice.category)
        )

        async def _update():
            async with AsyncSessionLocal() as db:
                inv = await db.get(Invoice, invoice_id)
                if inv:
                    inv.amount = amount
                    inv.date = date
                    # Pharmacy / uncategorised receipts skip ÖGK; other categories go to ÖGK first
                    inv.status = next_status
                    await db.commit()

        _run(_update())
        return {"invoice_id": invoice_id, "status": next_status.value}

    except Exception as exc:
        try:
            raise self.retry(exc=exc)
        except MaxRetriesExceededError:
            _run(_set_status(invoice_id, InvoiceStatus.FAILED))
            raise


@celery_app.task(bind=True, max_retries=3, default_retry_delay=120)
def submit_to_merkur(self, invoice_id: str) -> dict:
    """Submit invoice PDF to Merkur portal via headless Playwright.

    Idempotency: the invoice is moved READY_FOR_MERKUR -> MERKUR_SUBMITTING via
    an atomic compare-and-set BEFORE the portal is touched. If that CAS fails,
    a prior attempt already claimed this invoice (crashed mid-flight, or is
    concurrently running) — we do NOT click submit again.

    Once the CAS succeeds, a failure must NOT trigger Celery's automatic
    retry: the click may have already reached the real portal, so blindly
    retrying risks a genuine double submission. Any failure past this point
    marks the invoice FAILED immediately (no retry loop) and a human
    reconciles it against the real Merkur Postfach. Only the invoice lookup
    before the CAS is safe to retry, since nothing has been submitted yet.
    """
    try:
        invoice = _run(_get_invoice(invoice_id))
        if not invoice:
            raise ValueError(f"Invoice {invoice_id} not found")
    except Exception as exc:
        try:
            raise self.retry(exc=exc)
        except MaxRetriesExceededError:
            raise

    if invoice.status != InvoiceStatus.READY_FOR_MERKUR:
        return {
            "invoice_id": invoice_id,
            "status": invoice.status.value,
            "skipped": True,
            "reason": f"invoice not in READY_FOR_MERKUR (was {invoice.status.value})",
        }

    claimed = _run(_try_transition(
        invoice_id, InvoiceStatus.READY_FOR_MERKUR, InvoiceStatus.MERKUR_SUBMITTING
    ))
    if not claimed:
        return {"invoice_id": invoice_id, "status": "MERKUR_SUBMITTING", "skipped": True}

    try:
        if settings.merkur_dry_run:
            print(f"[DRY RUN] Skipping Merkur portal submission for invoice {invoice_id}", flush=True)
        else:
            bot = MerkurBot()
            date_str = _portal_date(invoice.date)
            success = _run(bot.submit_pharmacy_receipt(
                invoice_pdf=invoice.file_path,
                amount=invoice.amount or 0.0,
                date=date_str,
                patient_name=invoice.patient_name or "",
            ))
            if not success:
                # The click may or may not have actually gone through (the
                # success heuristic is imperfect) — treat as failed, do not retry.
                raise RuntimeError("Merkur submission did not return a success signal")

        _run(_set_status(invoice_id, InvoiceStatus.MERKUR_SUBMITTED))
        # Finalization (BenefitUsage + terminal status) now happens in sync_merkur_inbox
        # once Merkur places the result PDF in the Postfach.
        return {"invoice_id": invoice_id, "status": "MERKUR_SUBMITTED"}

    except Exception:
        # No automatic retry here — see docstring. The invoice is left
        # discoverable as FAILED instead of silently stuck in MERKUR_SUBMITTING.
        _run(_set_status(invoice_id, InvoiceStatus.FAILED))
        raise


@celery_app.task(bind=True, max_retries=3, default_retry_delay=120)
def submit_to_oegk(self, invoice_id: str) -> dict:
    """Submit invoice to ÖGK (persistent context, user handles 2FA).

    Same idempotency contract as submit_to_merkur: READY_FOR_OEGK ->
    OEGK_SUBMITTING is claimed atomically BEFORE the portal is touched, and any
    failure after the claim marks the invoice FAILED without a Celery retry,
    because the click may already have reached the real portal. Only the
    pre-claim invoice lookup is safe to retry.
    """
    try:
        invoice = _run(_get_invoice(invoice_id))
        if not invoice:
            raise ValueError(f"Invoice {invoice_id} not found")
    except Exception as exc:
        raise self.retry(exc=exc)

    if invoice.status != InvoiceStatus.READY_FOR_OEGK:
        return {
            "invoice_id": invoice_id,
            "status": invoice.status.value,
            "skipped": True,
            "reason": f"invoice not in READY_FOR_OEGK (was {invoice.status.value})",
        }

    if invoice.amount is None or invoice.date is None:
        _run(_set_status(invoice_id, InvoiceStatus.NEEDS_REVIEW))
        return {"invoice_id": invoice_id, "status": "NEEDS_REVIEW", "skipped": True}

    # Fetch the file BEFORE claiming: a failed download is safe to retry,
    # nothing has touched the portal yet.
    try:
        local_pdf = _ensure_local_file(invoice)
    except Exception as exc:
        raise self.retry(exc=exc)

    claimed = _run(_try_transition(
        invoice_id, InvoiceStatus.READY_FOR_OEGK, InvoiceStatus.OEGK_SUBMITTING
    ))
    if not claimed:
        return {"invoice_id": invoice_id, "status": "OEGK_SUBMITTING", "skipped": True}

    try:
        bot = OegkBot()
        success = _run(bot.submit_invoice(
            invoice_pdf=local_pdf,
            amount=invoice.amount,
            date=_portal_date(invoice.date),
        ))
        if not success:
            # The click may or may not have gone through — fail, do not retry.
            raise RuntimeError("ÖGK submission did not return a success signal")

        _run(_set_status(invoice_id, InvoiceStatus.OEGK_SUBMITTED))
        return {"invoice_id": invoice_id, "status": "OEGK_SUBMITTED"}

    except Exception:
        _run(_set_status(invoice_id, InvoiceStatus.FAILED))
        raise


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


@celery_app.task
def scan_unused_benefits() -> dict:
    """
    Daily scan for under-used yearly/once-per-year BUDGET/PROGRAM benefits
    whose reset date is within 8 weeks.  Results are served at query time via
    /dashboard/summary — this task is a no-op stub that triggers the logic
    on demand so it can also be called manually for testing.
    """
    return _run(_scan_unused_benefits_async())


_UNUSED_LEAD_DAYS = 56
_YEARLY_RESET_PERIODS = {ResetPeriod.CALENDAR_YEAR, ResetPeriod.ONCE_PER_YEAR, ResetPeriod.INSURANCE_YEAR}


async def _scan_unused_benefits_async() -> dict:
    """
    Iterate all per-person BUDGET/PROGRAM benefits with yearly resets.
    Log any reminders that should fire within the lead window.
    The dashboard endpoint computes the same logic at query time; this task
    can be extended later to push notifications or store a reminder model.
    """
    from datetime import date

    today = date.today()
    current_year = today.year
    reminder_count = 0

    async with AsyncSessionLocal() as db:
        rules_result = await db.execute(
            select(BenefitRule).where(
                BenefitRule.reset_period.in_([p.value for p in _YEARLY_RESET_PERIODS]),
                BenefitRule.benefit_kind.in_([BenefitKind.BUDGET.value, BenefitKind.PROGRAM.value]),
            )
        )
        rules = rules_result.scalars().all()

        # Pre-fetch person names
        person_names: dict[str, str] = {}
        persons_result = await db.execute(
            select(InsuredPerson, Tariff)
            .join(Tariff, Tariff.insured_person_id == InsuredPerson.id)
        )
        for person, tariff in persons_result:
            person_names[str(tariff.id)] = person.full_name

        for rule in rules:
            if rule.reset_period in (ResetPeriod.CALENDAR_YEAR, ResetPeriod.ONCE_PER_YEAR):
                reset_date = date(current_year, 12, 31)
            elif rule.reset_period == ResetPeriod.INSURANCE_YEAR:
                candidate = date(current_year, 10, 1)
                reset_date = candidate if candidate >= today else date(current_year + 1, 10, 1)
            else:
                continue

            days_until = (reset_date - today).days
            if days_until < 0 or days_until > _UNUSED_LEAD_DAYS:
                continue

            used_result = await db.execute(
                select(func.coalesce(func.sum(BenefitUsage.amount_used), 0.0)).where(
                    BenefitUsage.benefit_rule_id == rule.id
                )
            )
            used = float(used_result.scalar() or 0.0)

            if rule.benefit_kind == BenefitKind.PROGRAM:
                should_alert = used == 0
            else:
                pct_used = (used / rule.limit_amount * 100) if rule.limit_amount else 100
                should_alert = pct_used < 30

            if should_alert:
                person_name = person_names.get(str(rule.tariff_id), "unbekannt")
                print(
                    f"[scan_unused_benefits] REMINDER: {rule.benefit_name}"
                    f" ({person_name}) — {days_until}d until reset ({reset_date})",
                    flush=True,
                )
                reminder_count += 1

    return {"reminders_due": reminder_count}


async def _oegk_submitted_ids(invoice_id: str | None = None) -> list[tuple[str, str]]:
    """(invoice_id, user_id) of invoices awaiting an ÖGK refund."""
    async with AsyncSessionLocal() as db:
        stmt = select(Invoice.id, Invoice.user_id).where(Invoice.status == InvoiceStatus.OEGK_SUBMITTED)
        if invoice_id:
            stmt = stmt.where(Invoice.id == invoice_id)
        rows = (await db.execute(stmt)).all()
        return [(str(r[0]), str(r[1])) for r in rows]


@celery_app.task
def poll_oegk_refunds() -> dict:
    """Daily: fan out poll_oegk_refund for every invoice waiting on ÖGK."""
    waiting = _run(_oegk_submitted_ids())
    for invoice_id, _ in waiting:
        poll_oegk_refund.delay(invoice_id)
    return {"polled": len(waiting)}


@celery_app.task(bind=True)
def poll_oegk_refund(self, invoice_id: str) -> dict:
    """Check the ÖGK portal for a refund PDF for an OEGK_SUBMITTED invoice.

    No Celery retry loop: refunds take days or weeks, so poll_oegk_refunds
    simply asks again tomorrow. The portal does not (yet) tell us which
    invoice a refund document belongs to, so the invoice only advances when it
    is the user's single invoice awaiting a refund; with several in flight the
    PDF is saved but the invoices stay put for manual matching.
    """
    invoice = _run(_get_invoice(invoice_id))
    if not invoice:
        raise ValueError(f"Invoice {invoice_id} not found")
    if invoice.status != InvoiceStatus.OEGK_SUBMITTED:
        return {"invoice_id": invoice_id, "status": invoice.status.value, "skipped": True}

    # Output directory is derived server-side, never taken from a caller.
    output_dir = Path(settings.storage_root) / str(invoice.user_id) / "oegk_refunds"
    output_dir.mkdir(parents=True, exist_ok=True)

    refund_path = _run(OegkBot().download_refund_pdf(str(output_dir)))
    if not refund_path:
        return {"invoice_id": invoice_id, "status": "OEGK_SUBMITTED", "refund": "pending"}

    in_flight = [
        i for i, u in _run(_oegk_submitted_ids()) if u == str(invoice.user_id)
    ]
    if len(in_flight) != 1:
        return {
            "invoice_id": invoice_id,
            "status": "OEGK_SUBMITTED",
            "refund_pdf": refund_path,
            "refund": "needs_manual_match",
        }

    # Refund received: the ÖGK leg is done; the Merkur leg is ready to submit.
    _run(_set_status(invoice_id, InvoiceStatus.OEGK_REFUNDED))
    _run(_set_status(invoice_id, InvoiceStatus.READY_FOR_MERKUR))
    return {"invoice_id": invoice_id, "status": "READY_FOR_MERKUR", "refund_pdf": refund_path}
