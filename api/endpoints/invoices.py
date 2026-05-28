import shutil
import uuid
from pathlib import Path
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.dependencies import get_current_user
from core.config import get_settings
from core.database import get_db
from models.domain import FamilyMember, Invoice, InvoiceStatus, User
from schemas.payload import InvoiceCreate, InvoiceRead, InvoiceStatusUpdate
from workers.tasks import run_ocr, submit_to_merkur

_TERMINAL_STATUSES = {
    InvoiceStatus.COMPLETED,
    InvoiceStatus.MERKUR_REIMBURSED,
    InvoiceStatus.MERKUR_REJECTED,
}

settings = get_settings()

_ALLOWED_MIME_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "application/pdf",
}

router = APIRouter(prefix="/invoices", tags=["invoices"])


@router.post("/upload", response_model=InvoiceRead, status_code=status.HTTP_201_CREATED)
async def upload_invoice(
    file: Annotated[UploadFile, File(...)],
    benefit_rule_id: Annotated[UUID | None, Form()] = None,
    family_member_id: Annotated[UUID | None, Form()] = None,
    category: Annotated[str | None, Form()] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if file.content_type not in _ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file type: {file.content_type}. Allowed: jpeg, png, webp, pdf.",
        )

    ext = file.filename.rsplit(".", 1)[-1].lower() if file.filename and "." in file.filename else "jpg"
    dest_dir = Path(settings.storage_root) / str(current_user.id)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / f"{uuid.uuid4()}.{ext}"

    with dest_path.open("wb") as out:
        shutil.copyfileobj(file.file, out)

    invoice = Invoice(
        user_id=current_user.id,
        file_path=str(dest_path),
        benefit_rule_id=benefit_rule_id,
        family_member_id=family_member_id,
        category=category,
    )
    db.add(invoice)
    await db.commit()
    await db.refresh(invoice)

    run_ocr.delay(str(invoice.id))
    return invoice


@router.post("/", response_model=InvoiceRead, status_code=status.HTTP_201_CREATED)
async def create_invoice(
    payload: InvoiceCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    invoice = Invoice(user_id=current_user.id, **payload.model_dump())
    db.add(invoice)
    await db.commit()
    await db.refresh(invoice)

    # Kick off OCR immediately as a background Celery task
    run_ocr.delay(str(invoice.id))

    return invoice


@router.get("/", response_model=list[InvoiceRead])
async def list_invoices(
    member_key: str | None = Query(default=None, description="Filter by family member key"),
    status_group: str | None = Query(default=None, description="all | in_progress | completed"),
    search: str | None = Query(default=None, description="Case-insensitive search on provider_name"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from sqlalchemy import and_, or_
    stmt = select(Invoice).where(Invoice.user_id == current_user.id)

    if member_key:
        member_sub = select(FamilyMember.id).where(
            FamilyMember.user_id == current_user.id,
            FamilyMember.member_key == member_key,
        ).scalar_subquery()
        stmt = stmt.where(Invoice.family_member_id == member_sub)

    if status_group == "in_progress":
        stmt = stmt.where(Invoice.status.notin_(_TERMINAL_STATUSES))
    elif status_group == "completed":
        stmt = stmt.where(Invoice.status.in_(_TERMINAL_STATUSES))

    if search:
        stmt = stmt.where(Invoice.provider_name.ilike(f"%{search}%"))

    stmt = (
        stmt.options(selectinload(Invoice.merkur_document))
        .order_by(Invoice.created_at.desc())
    )
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/{invoice_id}", response_model=InvoiceRead)
async def get_invoice(
    invoice_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    invoice = await db.scalar(
        select(Invoice)
        .where(Invoice.id == invoice_id)
        .options(selectinload(Invoice.merkur_document))
    )
    _assert_owned(invoice, current_user.id)
    return invoice


@router.patch("/{invoice_id}/status", response_model=InvoiceRead)
async def update_invoice_status(
    invoice_id: UUID,
    payload: InvoiceStatusUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    invoice = await db.get(Invoice, invoice_id)
    _assert_owned(invoice, current_user.id)
    invoice.status = payload.status
    await db.commit()
    await db.refresh(invoice)
    return invoice


@router.post("/{invoice_id}/submit-merkur", response_model=InvoiceRead)
async def trigger_merkur_submission(
    invoice_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    invoice = await db.get(Invoice, invoice_id)
    _assert_owned(invoice, current_user.id)

    if invoice.status != InvoiceStatus.READY_FOR_MERKUR:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Invoice must be in READY_FOR_MERKUR state, current: {invoice.status}",
        )

    submit_to_merkur.delay(str(invoice_id))
    return invoice


def _assert_owned(invoice: Invoice | None, user_id: UUID) -> None:
    if not invoice:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")
    if invoice.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
