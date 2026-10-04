"""
Webhook endpoint for future integrations (e.g. ÖGK notifying us that a
refund document is ready). Placeholder for Phase 2 (the ÖGK submission arm
is not yet wired up), but gated with a shared secret since it's reachable
without a logged-in user.
"""
from fastapi import APIRouter, Header, HTTPException, Request, status

from core.config import get_settings

settings = get_settings()

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


def _verify_webhook_secret(x_webhook_secret: str | None) -> None:
    if not settings.webhook_secret or x_webhook_secret != settings.webhook_secret:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid webhook secret")


@router.post("/oegk-refund-ready")
async def oegk_refund_ready(
    request: Request,
    x_webhook_secret: str | None = Header(default=None),
):
    """
    ÖGK can POST here when a refund PDF is ready.
    The invoice_id is parsed and the appropriate poll_oegk_refund task is
    triggered; the output directory is derived server-side, not taken from
    the request body.
    """
    _verify_webhook_secret(x_webhook_secret)

    body = await request.json()
    invoice_id = body.get("invoice_id")

    if not invoice_id:
        return {"status": "ignored", "reason": "missing invoice_id"}

    from workers.tasks import poll_oegk_refund
    poll_oegk_refund.delay(invoice_id)

    return {"status": "accepted", "invoice_id": invoice_id}
