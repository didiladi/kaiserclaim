"""
Webhook endpoint for future integrations (e.g. ÖGK notifying us that a
refund document is ready). Placeholder for Phase 2 (the ÖGK submission arm
is not yet wired up), but gated with a shared secret since it's reachable
without a logged-in user.
"""
import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import get_settings
from core.database import get_db
from models.domain import Invoice

settings = get_settings()

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


def _verify_webhook_secret(x_webhook_secret: str | None) -> None:
    if not settings.webhook_secret or x_webhook_secret != settings.webhook_secret:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid webhook secret")


@router.post("/oegk-refund-ready")
async def oegk_refund_ready(
    request: Request,
    x_webhook_secret: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
):
    """
    ÖGK can POST here when a refund PDF is ready.
    The invoice_id only identifies the user: a refund sync is queued for them
    (it downloads and matches every new PDF); nothing path-like is taken from
    the request body.
    """
    _verify_webhook_secret(x_webhook_secret)

    body = await request.json()
    invoice_id = body.get("invoice_id")

    if not invoice_id:
        return {"status": "ignored", "reason": "missing invoice_id"}

    from workers.tasks import sync_oegk_refunds

    try:
        invoice = await db.get(Invoice, uuid.UUID(str(invoice_id)))
    except ValueError:
        invoice = None
    if not invoice:
        return {"status": "ignored", "reason": "unknown invoice_id"}

    sync_oegk_refunds.delay(str(invoice.user_id))
    return {"status": "accepted", "invoice_id": invoice_id}
