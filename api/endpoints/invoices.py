from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_current_user
from core.database import get_db
from models.domain import Invoice, InvoiceStatus, User
from schemas.payload import InvoiceCreate, InvoiceRead, InvoiceStatusUpdate
from workers.tasks import run_ocr, submit_to_merkur

router = APIRouter(prefix="/invoices", tags=["invoices"])


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
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Invoice).where(Invoice.user_id == current_user.id).order_by(Invoice.created_at.desc())
    )
    return result.scalars().all()


@router.get("/{invoice_id}", response_model=InvoiceRead)
async def get_invoice(
    invoice_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    invoice = await db.get(Invoice, invoice_id)
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
