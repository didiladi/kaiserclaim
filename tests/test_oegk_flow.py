"""
Tests for the ÖGK arm: category routing, idempotent submission, refund polling.

Same constraints as test_task_status_transitions.py (sync tests, NullPool,
no real Playwright). OegkBot is always patched.

Refund-matching tests use a throwaway user per test: poll_oegk_refund counts a
user's in-flight OEGK_SUBMITTED invoices, so a shared user would make them
depend on leftover rows in the dev database.
"""
import asyncio
import uuid
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from models.domain import Invoice, InvoiceStatus, User
from schemas.payload import first_submission_status
from tests.conftest import TEST_USER_ID, api_url
from tests.test_task_status_transitions import (  # also installs the NullPool engine
    _TestSession,
    _get_status,
    _run_task,
)
from workers import tasks as tasks_module
from workers.tasks import _ensure_local_file, celery_app, poll_oegk_refund, run_ocr, submit_to_oegk


_FIXTURE = Path("/tmp/kaiserclaim-test-storage/fixture.pdf")
_FIXTURE.parent.mkdir(parents=True, exist_ok=True)
_FIXTURE.write_bytes(b"%PDF-1.4 test")


async def _create(status, *, user_id=TEST_USER_ID, category=None, amount=12.34,
                  date=datetime(2026, 1, 15, 12, tzinfo=timezone.utc)) -> str:
    async with _TestSession() as db:
        inv = Invoice(
            user_id=user_id,
            file_path="/tmp/kaiserclaim-test-storage/fixture.pdf",
            status=status,
            category=category,
            amount=amount,
            date=date,
        )
        db.add(inv)
        await db.commit()
        return str(inv.id)


async def _create_user() -> uuid.UUID:
    async with _TestSession() as db:
        user = User(email=f"oegk-test-{uuid.uuid4()}@example.invalid")
        db.add(user)
        await db.commit()
        return user.id


def _make(status, **kw) -> str:
    return asyncio.run(_create(status, **kw))


# ---------------------------------------------------------------------------
# Routing
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "category,expected",
    [
        (None, InvoiceStatus.READY_FOR_MERKUR),
        ("", InvoiceStatus.READY_FOR_MERKUR),
        ("Medikamente", InvoiceStatus.READY_FOR_MERKUR),
        ("Apotheke", InvoiceStatus.READY_FOR_MERKUR),
        ("Arzt", InvoiceStatus.READY_FOR_OEGK),
        ("Physiotherapie", InvoiceStatus.READY_FOR_OEGK),
    ],
)
def test_first_submission_status(category, expected):
    assert first_submission_status(category) == expected


def test_run_ocr_routes_non_pharmacy_to_oegk():
    invoice_id = _make(InvoiceStatus.RECEIVED, category="Arzt", amount=None, date=None)

    class _Rksv:
        date = datetime(2026, 1, 15)
        amount = 80.0

    with patch("workers.tasks.extract_rksv_from_image", return_value=_Rksv()), \
         patch("services.rksv_parser.extract_qr_codes", return_value=["dummy"]):
        result = _run_task(run_ocr.run, invoice_id)

    assert result["status"] == "READY_FOR_OEGK"
    assert _get_status(invoice_id) == InvoiceStatus.READY_FOR_OEGK


# ---------------------------------------------------------------------------
# submit_to_oegk
# ---------------------------------------------------------------------------

def test_submit_to_oegk_happy_path():
    invoice_id = _make(InvoiceStatus.READY_FOR_OEGK, category="Arzt")
    with patch("workers.tasks.OegkBot.submit_invoice", new=AsyncMock(return_value=True)) as bot:
        result = _run_task(submit_to_oegk.run, invoice_id)

    assert result["status"] == "OEGK_SUBMITTED"
    assert _get_status(invoice_id) == InvoiceStatus.OEGK_SUBMITTED
    assert bot.await_args.kwargs["date"] == "15.01.2026"


def test_submit_to_oegk_date_is_vienna_local():
    # 23:30 UTC on 14 Jan is already 15 Jan in Vienna.
    invoice_id = _make(
        InvoiceStatus.READY_FOR_OEGK, date=datetime(2026, 1, 14, 23, 30, tzinfo=timezone.utc)
    )
    with patch("workers.tasks.OegkBot.submit_invoice", new=AsyncMock(return_value=True)) as bot:
        _run_task(submit_to_oegk.run, invoice_id)

    assert bot.await_args.kwargs["date"] == "15.01.2026"


def test_submit_to_oegk_skips_when_not_ready():
    invoice_id = _make(InvoiceStatus.OEGK_SUBMITTING)
    with patch(
        "workers.tasks.OegkBot.submit_invoice",
        new=AsyncMock(side_effect=AssertionError("bot must not be invoked")),
    ):
        result = _run_task(submit_to_oegk.run, invoice_id)

    assert result["skipped"] is True
    assert _get_status(invoice_id) == InvoiceStatus.OEGK_SUBMITTING


def test_submit_to_oegk_missing_amount_goes_to_review():
    invoice_id = _make(InvoiceStatus.READY_FOR_OEGK, amount=None)
    with patch(
        "workers.tasks.OegkBot.submit_invoice",
        new=AsyncMock(side_effect=AssertionError("bot must not be invoked")),
    ):
        result = _run_task(submit_to_oegk.run, invoice_id)

    assert result["status"] == "NEEDS_REVIEW"
    assert _get_status(invoice_id) == InvoiceStatus.NEEDS_REVIEW


def test_submit_to_oegk_bot_error_marks_failed_without_retry():
    invoice_id = _make(InvoiceStatus.READY_FOR_OEGK)
    bot = AsyncMock(side_effect=RuntimeError("2FA timeout"))
    with patch("workers.tasks.OegkBot.submit_invoice", new=bot):
        with pytest.raises(RuntimeError):
            _run_task(submit_to_oegk.run, invoice_id)

    assert bot.await_count == 1
    assert _get_status(invoice_id) == InvoiceStatus.FAILED


def test_submit_to_oegk_no_success_signal_marks_failed():
    invoice_id = _make(InvoiceStatus.READY_FOR_OEGK)
    with patch("workers.tasks.OegkBot.submit_invoice", new=AsyncMock(return_value=False)):
        with pytest.raises(RuntimeError):
            _run_task(submit_to_oegk.run, invoice_id)

    assert _get_status(invoice_id) == InvoiceStatus.FAILED


# ---------------------------------------------------------------------------
# poll_oegk_refund
# ---------------------------------------------------------------------------

def _poll(invoice_id, refund_path):
    with patch("workers.tasks.OegkBot.download_refund_pdf", new=AsyncMock(return_value=refund_path)):
        return _run_task(poll_oegk_refund.run, invoice_id)


def test_poll_refund_pending_leaves_status():
    user = asyncio.run(_create_user())
    invoice_id = _make(InvoiceStatus.OEGK_SUBMITTED, user_id=user)

    result = _poll(invoice_id, None)

    assert result["refund"] == "pending"
    assert _get_status(invoice_id) == InvoiceStatus.OEGK_SUBMITTED


def test_poll_refund_single_invoice_advances_to_merkur():
    user = asyncio.run(_create_user())
    invoice_id = _make(InvoiceStatus.OEGK_SUBMITTED, user_id=user)

    result = _poll(invoice_id, "/tmp/kaiserclaim-test-storage/refund.pdf")

    assert result["status"] == "READY_FOR_MERKUR"
    assert _get_status(invoice_id) == InvoiceStatus.READY_FOR_MERKUR


def test_poll_refund_ambiguous_needs_manual_match():
    user = asyncio.run(_create_user())
    first = _make(InvoiceStatus.OEGK_SUBMITTED, user_id=user)
    second = _make(InvoiceStatus.OEGK_SUBMITTED, user_id=user)

    result = _poll(first, "/tmp/kaiserclaim-test-storage/refund.pdf")

    assert result["refund"] == "needs_manual_match"
    assert _get_status(first) == InvoiceStatus.OEGK_SUBMITTED
    assert _get_status(second) == InvoiceStatus.OEGK_SUBMITTED


def test_poll_refund_ignores_invoice_not_awaiting_refund():
    invoice_id = _make(InvoiceStatus.READY_FOR_MERKUR)
    with patch(
        "workers.tasks.OegkBot.download_refund_pdf",
        new=AsyncMock(side_effect=AssertionError("bot must not be invoked")),
    ):
        result = _run_task(poll_oegk_refund.run, invoice_id)

    assert result["skipped"] is True


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_submit_oegk_endpoint_queues_task(client):
    invoice_id = await _create(InvoiceStatus.READY_FOR_OEGK)
    with patch("api.endpoints.invoices.submit_to_oegk.delay") as delay:
        r = await client.post(api_url(f"/invoices/{invoice_id}/submit-oegk"))

    assert r.status_code == 200
    delay.assert_called_once_with(invoice_id)


@pytest.mark.asyncio
async def test_submit_oegk_endpoint_rejects_wrong_state(client):
    invoice_id = await _create(InvoiceStatus.READY_FOR_MERKUR)
    with patch("api.endpoints.invoices.submit_to_oegk.delay") as delay:
        r = await client.post(api_url(f"/invoices/{invoice_id}/submit-oegk"))

    assert r.status_code == 409
    delay.assert_not_called()


@pytest.mark.asyncio
async def test_correction_routes_to_oegk_for_non_pharmacy(client):
    invoice_id = await _create(
        InvoiceStatus.NEEDS_REVIEW, category="Arzt", amount=None, date=None
    )
    r = await client.patch(
        api_url(f"/invoices/{invoice_id}"),
        json={"amount": 42, "date": "2026-02-01T00:00:00"},
    )

    assert r.status_code == 200
    assert r.json()["status"] == "READY_FOR_OEGK"


# ---------------------------------------------------------------------------
# Desktop worker: queue routing + file fetch
# ---------------------------------------------------------------------------

def test_browser_tasks_routed_to_oegk_queue():
    routes = celery_app.conf.task_routes
    assert routes["workers.tasks.submit_to_oegk"]["queue"] == "oegk"
    assert routes["workers.tasks.poll_oegk_refund"]["queue"] == "oegk"
    # The fan-out task needs no browser and stays on the default (cluster) queue.
    assert "workers.tasks.poll_oegk_refunds" not in routes


def test_ensure_local_file_returns_existing_path():
    inv = Invoice(id=uuid.uuid4(), user_id=TEST_USER_ID, file_path=str(_FIXTURE))
    assert _ensure_local_file(inv) == str(_FIXTURE)


def test_ensure_local_file_missing_without_api_url_raises():
    inv = Invoice(id=uuid.uuid4(), user_id=TEST_USER_ID, file_path="/nonexistent/x.pdf")
    with patch.object(tasks_module.settings, "api_base_url", ""):
        with pytest.raises(FileNotFoundError):
            _ensure_local_file(inv)


def test_submit_to_oegk_unfetchable_file_retries_without_claiming():
    """A missing file must not burn the claim: nothing touched the portal."""
    invoice_id = _make(InvoiceStatus.READY_FOR_OEGK)
    with patch("workers.tasks._ensure_local_file", side_effect=FileNotFoundError("gone")), \
         patch(
             "workers.tasks.OegkBot.submit_invoice",
             new=AsyncMock(side_effect=AssertionError("bot must not be invoked")),
         ):
        with pytest.raises(Exception):  # celery Retry (or the original error)
            _run_task(submit_to_oegk.run, invoice_id)

    assert _get_status(invoice_id) == InvoiceStatus.READY_FOR_OEGK


@pytest.mark.asyncio
async def test_invoice_file_endpoint_serves_stored_file(client):
    invoice_id = await _create(InvoiceStatus.READY_FOR_OEGK)
    from core.config import get_settings
    with patch.object(get_settings(), "storage_root", "/tmp/kaiserclaim-test-storage"):
        r = await client.get(api_url(f"/invoices/{invoice_id}/file"))
    assert r.status_code == 200
    assert r.content.startswith(b"%PDF")


@pytest.mark.asyncio
async def test_invoice_file_endpoint_refuses_path_outside_storage(client):
    invoice_id = await _create(InvoiceStatus.READY_FOR_OEGK)
    async with _TestSession() as db:
        inv = await db.get(Invoice, invoice_id)
        inv.file_path = "/etc/hostname"
        await db.commit()
    r = await client.get(api_url(f"/invoices/{invoice_id}/file"))
    assert r.status_code == 404
