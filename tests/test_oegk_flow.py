"""
Tests for the ÖGK arm: category routing, idempotent submission, refund sync.

Same constraints as test_task_status_transitions.py (sync tests, NullPool,
no real Playwright). OegkBot is always patched.

PDF matching itself is covered in test_oegk_ingest.py.
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
from workers.tasks import _ensure_local_file, celery_app, run_ocr, submit_to_oegk, sync_oegk_refunds


@pytest.fixture(autouse=True)
def _submit_enabled():
    """Submission is off by default; these tests exercise the enabled path."""
    from core.config import get_settings
    with patch.object(get_settings(), "oegk_submit_enabled", True):
        yield


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
# submission switch (off until the meine ÖGK submit flow is calibrated)
# ---------------------------------------------------------------------------

def test_submit_to_oegk_disabled_leaves_invoice_untouched():
    invoice_id = _make(InvoiceStatus.READY_FOR_OEGK, category="Arzt")
    with patch.object(tasks_module.settings, "oegk_submit_enabled", False), \
         patch(
             "workers.tasks.OegkBot.submit_invoice",
             new=AsyncMock(side_effect=AssertionError("bot must not be invoked")),
         ):
        result = _run_task(submit_to_oegk.run, invoice_id)

    assert result["skipped"] is True
    assert _get_status(invoice_id) == InvoiceStatus.READY_FOR_OEGK


@pytest.mark.asyncio
async def test_submit_oegk_endpoint_disabled_returns_501(client):
    from core.config import get_settings
    invoice_id = await _create(InvoiceStatus.READY_FOR_OEGK)
    with patch.object(get_settings(), "oegk_submit_enabled", False), \
         patch("api.endpoints.invoices.submit_to_oegk.delay") as delay:
        r = await client.post(api_url(f"/invoices/{invoice_id}/submit-oegk"))

    assert r.status_code == 501
    delay.assert_not_called()


# ---------------------------------------------------------------------------
# sync_oegk_refunds
# ---------------------------------------------------------------------------

def _sync(paths, outcomes):
    with patch("workers.tasks.OegkBot.download_refunds", new=AsyncMock(return_value=paths)) as bot, \
         patch("workers.tasks._ingest_refund_file", side_effect=outcomes) as ingest, \
         patch("services.notifier.notify") as notify:
        result = _run_task(sync_oegk_refunds.run, str(TEST_USER_ID))
    return result, bot, ingest, notify


def test_sync_counts_outcomes_and_notifies_only_for_new_unmatched():
    result, bot, ingest, notify = _sync(
        ["/tmp/a.pdf", "/tmp/b.pdf", "/tmp/c.pdf", "/tmp/d.pdf"],
        [
            {"outcome": "linked", "is_new": True},
            {"outcome": "duplicate", "is_new": False},
            {"outcome": "unmatched", "is_new": True},
            {"outcome": "ambiguous", "is_new": False},  # seen before: no repeat notification
        ],
    )

    assert result["downloaded"] == 4
    assert result["linked"] == 1 and result["unmatched"] == 1 and result["duplicate"] == 1
    assert ingest.call_count == 4
    notify.assert_called_once()
    assert "1 new" in notify.call_args.args[0]


def test_sync_without_pdfs_does_nothing():
    result, bot, ingest, notify = _sync([], [])

    assert result["downloaded"] == 0
    ingest.assert_not_called()
    notify.assert_not_called()


def test_sync_passes_since_to_bot():
    with patch("workers.tasks.OegkBot.download_refunds", new=AsyncMock(return_value=[])) as bot:
        _run_task(sync_oegk_refunds.run, str(TEST_USER_ID), "01.01.2025")

    assert bot.await_args.args[1] == "01.01.2025"


def test_sync_cleans_up_download_dir_on_error():
    seen = {}

    async def _boom(_self, output_dir, since=None):
        seen["dir"] = Path(output_dir)
        seen["dir"].mkdir(parents=True)
        (seen["dir"] / "x.pdf").write_bytes(b"%PDF")
        raise RuntimeError("2FA timeout")

    with patch("workers.tasks.OegkBot.download_refunds", new=_boom):
        with pytest.raises(RuntimeError):
            _run_task(sync_oegk_refunds.run, str(TEST_USER_ID))

    assert not seen["dir"].exists()


def test_poll_fans_out_one_sync_per_waiting_user():
    user = asyncio.run(_create_user())
    _make(InvoiceStatus.OEGK_SUBMITTED, user_id=user)
    _make(InvoiceStatus.READY_FOR_OEGK, user_id=user)  # same user: still one sync
    with patch("workers.tasks.sync_oegk_refunds.apply_async") as apply_async:
        result = _run_task(tasks_module.poll_oegk_refunds.run)

    users = {c.kwargs["args"][0] for c in apply_async.call_args_list}
    assert str(user) in users
    assert len(users) == len(apply_async.call_args_list)  # no user queued twice
    assert all(c.kwargs["expires"] <= 24 * 3600 for c in apply_async.call_args_list)
    assert result["users"] == len(users)


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
    assert routes["workers.tasks.sync_oegk_refunds"]["queue"] == "oegk"
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
