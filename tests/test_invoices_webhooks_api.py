"""
API-level tests for two P0 fixes:
- POST /api/v1/invoices/ (raw file_path create) has been removed.
- POST /api/v1/webhooks/oegk-refund-ready requires the X-Webhook-Secret header.
"""
from unittest.mock import patch

import pytest

from core.config import get_settings
from tests.conftest import api_url


@pytest.mark.asyncio
async def test_raw_invoice_create_endpoint_removed(client):
    r = await client.post(api_url("/invoices/"), json={"file_path": "/etc/passwd"})
    assert r.status_code in (404, 405)


@pytest.mark.asyncio
async def test_webhook_rejects_missing_secret(client):
    r = await client.post(
        api_url("/webhooks/oegk-refund-ready"),
        json={"invoice_id": "11111111-1111-1111-1111-111111111111"},
    )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_webhook_rejects_wrong_secret(client):
    with patch.object(get_settings(), "webhook_secret", "correct-secret"):
        r = await client.post(
            api_url("/webhooks/oegk-refund-ready"),
            json={"invoice_id": "11111111-1111-1111-1111-111111111111"},
            headers={"X-Webhook-Secret": "wrong-secret"},
        )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_webhook_accepts_correct_secret(client):
    invoice_id = await _insert_invoice(InvoiceStatus.READY_FOR_OEGK)
    with patch.object(get_settings(), "webhook_secret", "correct-secret"):
        with patch("workers.tasks.sync_oegk_refunds.delay") as mock_delay:
            r = await client.post(
                api_url("/webhooks/oegk-refund-ready"),
                json={"invoice_id": invoice_id},
                headers={"X-Webhook-Secret": "correct-secret"},
            )
    assert r.status_code == 200
    assert r.json()["status"] == "accepted"
    mock_delay.assert_called_once_with(str(TEST_USER_ID))


@pytest.mark.asyncio
@pytest.mark.parametrize("bad_id", ["11111111-1111-1111-1111-111111111111", "not-a-uuid"])
async def test_webhook_ignores_unknown_invoice(client, bad_id):
    with patch.object(get_settings(), "webhook_secret", "correct-secret"):
        with patch("workers.tasks.sync_oegk_refunds.delay") as mock_delay:
            r = await client.post(
                api_url("/webhooks/oegk-refund-ready"),
                json={"invoice_id": bad_id},
                headers={"X-Webhook-Secret": "correct-secret"},
            )
    assert r.status_code == 200
    assert r.json()["status"] == "ignored"
    mock_delay.assert_not_called()


# ---------------------------------------------------------------------------
# PATCH /invoices/{id}: NEEDS_REVIEW recovery
# ---------------------------------------------------------------------------

from models.domain import Invoice, InvoiceStatus
from tests.conftest import TEST_USER_ID


async def _insert_invoice(status, amount=None, date=None) -> str:
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from tests.conftest import _TEST_DB_URL

    engine = create_async_engine(_TEST_DB_URL)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as db:
            inv = Invoice(
                user_id=TEST_USER_ID,
                file_path="/tmp/kaiserclaim-test-storage/fixture.pdf",
                status=status,
                amount=amount,
                date=date,
            )
            db.add(inv)
            await db.commit()
            return str(inv.id)
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_correct_needs_review_advances_when_complete(client):
    inv_id = await _insert_invoice(InvoiceStatus.NEEDS_REVIEW)
    r = await client.patch(
        api_url(f"/invoices/{inv_id}"),
        json={"amount": 19.9, "date": "2026-09-01T00:00:00"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "READY_FOR_MERKUR"
    assert r.json()["amount"] == 19.9


@pytest.mark.asyncio
async def test_correct_needs_review_stays_when_still_incomplete(client):
    inv_id = await _insert_invoice(InvoiceStatus.NEEDS_REVIEW)
    r = await client.patch(api_url(f"/invoices/{inv_id}"), json={"amount": 5})
    assert r.status_code == 200
    assert r.json()["status"] == "NEEDS_REVIEW"


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [InvoiceStatus.FAILED, InvoiceStatus.MERKUR_SUBMITTED])
async def test_correct_rejected_in_other_states(client, status):
    inv_id = await _insert_invoice(status)
    r = await client.patch(api_url(f"/invoices/{inv_id}"), json={"amount": 5})
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_correct_rejects_non_positive_amount(client):
    inv_id = await _insert_invoice(InvoiceStatus.NEEDS_REVIEW)
    r = await client.patch(api_url(f"/invoices/{inv_id}"), json={"amount": 0})
    assert r.status_code == 422
