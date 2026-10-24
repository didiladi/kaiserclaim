from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_current_user
from core.config import get_settings
from core.database import get_db
from models.domain import User
from schemas.payload import OegkIngestRead
from services.oegk_ingest import ingest_refund_pdf

router = APIRouter(prefix="/oegk", tags=["oegk"])

_MAX_PDF_BYTES = 10 * 1024 * 1024


@router.post("/refund-pdfs", response_model=OegkIngestRead)
async def upload_refund_pdf(
    file: UploadFile,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Receive a refund PDF from the desktop ÖGK worker: store, dedupe, match to an
    invoice and advance it to READY_FOR_MERKUR with the PDF attached."""
    content = await file.read(_MAX_PDF_BYTES + 1)
    if len(content) > _MAX_PDF_BYTES:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="PDF too large")
    result = await ingest_refund_pdf(db, current_user.id, content, get_settings().storage_root)
    return OegkIngestRead(outcome=result.outcome, document_id=result.document_id,
                          invoice_id=result.invoice_id, is_new=result.is_new)
