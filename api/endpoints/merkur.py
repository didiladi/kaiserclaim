from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_current_user
from core.database import get_db
from models.domain import MerkurDocument, User
from schemas.payload import MerkurDocumentRead
from workers.tasks import sync_merkur_inbox

router = APIRouter(prefix="/merkur", tags=["merkur"])


@router.post("/sync", status_code=202)
async def trigger_inbox_sync(
    full_history: bool = Query(default=False, description="Expand all years for a full backfill"),
    current_user: User = Depends(get_current_user),
):
    """Enqueue a Celery task to sync the Merkur Postfach inbox.

    Set full_history=true for the one-time backfill on a deployed instance.
    """
    task = sync_merkur_inbox.delay(full_history=full_history)
    return {"task_id": task.id, "full_history": full_history}


@router.get("/documents", response_model=list[MerkurDocumentRead])
async def list_merkur_documents(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all downloaded Merkur claim-result documents for the current user."""
    result = await db.execute(
        select(MerkurDocument)
        .where(MerkurDocument.user_id == current_user.id)
        .order_by(MerkurDocument.document_date.desc())
    )
    return result.scalars().all()
