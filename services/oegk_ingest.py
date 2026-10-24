"""
Store, dedupe, match and link one ÖGK refund PDF.

The PDF is downloaded by the desktop ÖGK worker but must end up on the cluster
volume, because the Merkur upload (photo + refund PDF) runs there. So the worker
sends each PDF to POST /oegk/refund-pdfs, which calls ingest_refund_pdf.
"""
import hashlib
import io
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain import (
    AttachmentKind, FamilyMember, Invoice, InvoiceAttachment, InvoiceStatus, OegkDocument,
)
from services.oegk_result_parser import OegkResult, parse_oegk_pdf

_VIENNA = ZoneInfo("Europe/Vienna")

# A refund arriving is proof the claim reached ÖGK, so invoices still marked
# READY_FOR_OEGK (submitted by hand), OEGK_SUBMITTING or FAILED are rescued too.
_AWAITING = [
    InvoiceStatus.READY_FOR_OEGK,
    InvoiceStatus.OEGK_SUBMITTING,
    InvoiceStatus.OEGK_SUBMITTED,
    InvoiceStatus.FAILED,
]
# READY_FOR_MERKUR can still receive the attachment (status stays as it is).
_CANDIDATES = _AWAITING + [InvoiceStatus.READY_FOR_MERKUR]


@dataclass
class IngestResult:
    outcome: str  # not_a_refund | duplicate | linked | unmatched | ambiguous
    document_id: Optional[UUID] = None
    invoice_id: Optional[UUID] = None
    is_new: bool = False  # the PDF was first seen in this call


def _invoice_day(inv: Invoice):
    dt = inv.date
    return (dt.astimezone(_VIENNA) if dt.tzinfo else dt).date()


def invoice_matches(inv: Invoice, member_svnr: Optional[str], r: OegkResult) -> bool:
    """Same patient, treatment day inside the PDF's service range, same invoice amount."""
    if inv.date is None or inv.amount is None:
        return False
    if not (r.service_from <= _invoice_day(inv) <= r.service_to):
        return False
    if abs(inv.amount - r.invoice_amount) > 0.01:
        return False
    if member_svnr:
        return member_svnr == r.patient_svnr
    if inv.patient_name:
        a, b = inv.patient_name.lower(), r.patient_name.lower()
        return a in b or b in a
    return True


async def _find_invoice(db: AsyncSession, user_id: UUID, r: OegkResult, doc_id: UUID) -> tuple[Optional[Invoice], int]:
    claimed = select(OegkDocument.invoice_id).where(
        OegkDocument.invoice_id.isnot(None), OegkDocument.id != doc_id
    )
    rows = (await db.execute(
        select(Invoice, FamilyMember.svnr)
        .outerjoin(FamilyMember, Invoice.family_member_id == FamilyMember.id)
        .where(
            Invoice.user_id == user_id,
            Invoice.status.in_(_CANDIDATES),
            Invoice.id.not_in(claimed),
        )
    )).all()
    matches = [inv for inv, svnr in rows if invoice_matches(inv, svnr, r)]
    return (matches[0] if len(matches) == 1 else None), len(matches)


async def ingest_refund_pdf(
    db: AsyncSession, user_id: UUID, content: bytes, storage_root: str
) -> IngestResult:
    result = parse_oegk_pdf(io.BytesIO(content))
    if result is None:
        return IngestResult("not_a_refund")

    # Per-user key: the global unique index must not collide across users.
    key = hashlib.sha256(f"{user_id}:{result.dedupe_key}".encode()).hexdigest()

    doc = (await db.execute(select(OegkDocument).where(OegkDocument.dedupe_key == key))).scalar_one_or_none()
    if doc is not None and doc.invoice_id is not None:
        return IngestResult("duplicate", doc.id, doc.invoice_id)

    is_new = doc is None
    if doc is None:
        target = Path(storage_root) / str(user_id) / "oegk_refunds" / f"{key[:16]}.pdf"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        doc = OegkDocument(
            user_id=user_id,
            dedupe_key=key,
            file_path=str(target),
            patient_name=result.patient_name,
            doctor_name=result.doctor_name,
            service_date=result.service_from,
            payout_date=result.payout_date,
            invoice_amount=result.invoice_amount,
            reimbursed_amount=result.reimbursed_amount,
        )
        db.add(doc)
        await db.flush()

    invoice, n_matches = await _find_invoice(db, user_id, result, doc.id)
    if invoice is None:
        await db.commit()
        return IngestResult("ambiguous" if n_matches > 1 else "unmatched", doc.id, is_new=is_new)

    doc.invoice_id = invoice.id
    doc.family_member_id = invoice.family_member_id
    db.add(InvoiceAttachment(invoice_id=invoice.id, kind=AttachmentKind.OEGK_REFUND.value, file_path=doc.file_path))
    # Conditional update: a concurrent run must not move an invoice twice.
    await db.execute(
        update(Invoice)
        .where(Invoice.id == invoice.id, Invoice.status.in_(_AWAITING))
        .values(status=InvoiceStatus.READY_FOR_MERKUR)
    )
    await db.commit()
    return IngestResult("linked", doc.id, invoice.id, is_new=is_new)
