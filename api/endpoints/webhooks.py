"""
Webhook endpoint for future integrations (e.g. ÖGK notifying us that a
refund document is ready). Placeholder for Phase 2.
"""
from fastapi import APIRouter, Request

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/oegk-refund-ready")
async def oegk_refund_ready(request: Request):
    """
    ÖGK can POST here when a refund PDF is ready.
    Body is parsed and the appropriate poll_oegk_refund task is triggered.
    """
    body = await request.json()
    invoice_id = body.get("invoice_id")
    output_dir = body.get("output_dir")

    if not invoice_id or not output_dir:
        return {"status": "ignored", "reason": "missing invoice_id or output_dir"}

    from workers.tasks import poll_oegk_refund
    poll_oegk_refund.delay(invoice_id, output_dir)

    return {"status": "accepted", "invoice_id": invoice_id}
