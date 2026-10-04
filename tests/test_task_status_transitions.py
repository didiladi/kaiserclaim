"""
Tests for the Celery task status transitions fixed in the P0 pass:
- submit_to_merkur is idempotent against retries/duplicate dispatch.
- run_ocr routes missing amount/date to NEEDS_REVIEW instead of silently
  advancing.
- Retry exhaustion marks the invoice FAILED instead of leaving it stuck.

Celery tasks in workers/tasks.py bridge into async code via `_run()`, which
calls asyncio.get_event_loop().run_until_complete(...) — this cannot be
nested inside an already-running event loop, so these tests are plain
(synchronous) functions, not `async def` / pytest.mark.asyncio, matching how
a real Celery worker thread calls them.

Every engine here uses NullPool: asyncpg connections are bound to the event
loop that created them, and each synchronous test drives its own separate
loop (via asyncio.run() or the task's own internal loop), so no connection
may be reused across a loop boundary.

Uses the DATABASE_URL from the environment/settings (NOT tests/conftest.py's
hardcoded `_TEST_DB_URL` constant — that constant always points at
localhost:5432 regardless of the DATABASE_URL env var, which is the local
docker-compose Postgres and may be a real, non-throwaway instance). MerkurBot
is monkeypatched — no real Playwright/portal calls happen here.
"""
import asyncio
import uuid
from unittest.mock import AsyncMock, patch

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

import core.database as database_module
from core.config import get_settings
from models.domain import Invoice, InvoiceStatus
from workers import tasks as tasks_module
from workers.tasks import _try_transition, run_ocr, submit_to_merkur

TEST_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
_TEST_DB_URL = get_settings().database_url

# Force workers.tasks' internal AsyncSessionLocal onto a NullPool engine so
# that connections never outlive the single event loop they were opened in.
database_module.engine = create_async_engine(_TEST_DB_URL, poolclass=NullPool)
database_module.AsyncSessionLocal = async_sessionmaker(
    database_module.engine, expire_on_commit=False
)
tasks_module.AsyncSessionLocal = database_module.AsyncSessionLocal

_TestSession = async_sessionmaker(
    create_async_engine(_TEST_DB_URL, poolclass=NullPool), expire_on_commit=False
)


def _run_task(fn, *args, **kwargs):
    """
    Call a Celery task's .run()/.apply() from a plain (non-async) test.

    On Python 3.12, once anything in this process has called asyncio.run()
    (as our own helpers below do), the "current event loop" for this thread
    is left as None, so a bare asyncio.get_event_loop() inside the task's
    `_run()` helper raises "There is no current event loop". Set a fresh one
    immediately before invoking the task.
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return fn(*args, **kwargs)
    finally:
        loop.close()
        asyncio.set_event_loop(None)


async def _make_invoice_async(status: InvoiceStatus, **overrides) -> str:
    async with _TestSession() as db:
        invoice = Invoice(
            user_id=TEST_USER_ID,
            file_path="/tmp/kaiserclaim-test-storage/fixture.pdf",
            status=status,
            amount=overrides.get("amount", 12.34),
            date=overrides.get("date"),
            patient_name=overrides.get("patient_name", "Test Patient"),
        )
        db.add(invoice)
        await db.commit()
        await db.refresh(invoice)
        return str(invoice.id)


async def _get_status_async(invoice_id: str) -> InvoiceStatus:
    async with _TestSession() as db:
        result = await db.execute(select(Invoice).where(Invoice.id == invoice_id))
        return result.scalar_one().status


def _make_invoice(status: InvoiceStatus, **overrides) -> str:
    return asyncio.run(_make_invoice_async(status, **overrides))


def _get_status(invoice_id: str) -> InvoiceStatus:
    return asyncio.run(_get_status_async(invoice_id))


def test_try_transition_cas_only_succeeds_once():
    invoice_id = _make_invoice(InvoiceStatus.READY_FOR_MERKUR)

    async def _both_attempts():
        first = await _try_transition(
            invoice_id, InvoiceStatus.READY_FOR_MERKUR, InvoiceStatus.MERKUR_SUBMITTING
        )
        second = await _try_transition(
            invoice_id, InvoiceStatus.READY_FOR_MERKUR, InvoiceStatus.MERKUR_SUBMITTING
        )
        return first, second

    first, second = asyncio.run(_both_attempts())

    assert first is True
    assert second is False
    assert _get_status(invoice_id) == InvoiceStatus.MERKUR_SUBMITTING


def test_submit_to_merkur_dry_run_happy_path():
    invoice_id = _make_invoice(InvoiceStatus.READY_FOR_MERKUR)

    with patch.object(tasks_module.settings, "merkur_dry_run", True):
        result = _run_task(submit_to_merkur.run, invoice_id)

    assert result["status"] == "MERKUR_SUBMITTED"
    assert _get_status(invoice_id) == InvoiceStatus.MERKUR_SUBMITTED


def test_submit_to_merkur_skips_when_not_ready():
    """An invoice already MERKUR_SUBMITTING/MERKUR_SUBMITTED must never be re-clicked."""
    invoice_id = _make_invoice(InvoiceStatus.MERKUR_SUBMITTING)

    with patch(
        "workers.tasks.MerkurBot.submit_pharmacy_receipt",
        new=AsyncMock(side_effect=AssertionError("bot must not be invoked")),
    ):
        with patch.object(tasks_module.settings, "merkur_dry_run", False):
            result = _run_task(submit_to_merkur.run, invoice_id)

    assert result["skipped"] is True
    assert _get_status(invoice_id) == InvoiceStatus.MERKUR_SUBMITTING


def test_submit_to_merkur_failure_after_cas_marks_failed_without_retry():
    """
    Once the invoice is claimed (CAS to MERKUR_SUBMITTING), a bot failure must
    mark FAILED immediately with no automatic retry — retrying here risks a
    real double-submission to the portal, since the click may have already
    gone through.
    """
    invoice_id = _make_invoice(InvoiceStatus.READY_FOR_MERKUR)

    with patch(
        "workers.tasks.MerkurBot.submit_pharmacy_receipt",
        new=AsyncMock(side_effect=RuntimeError("portal unreachable")),
    ):
        with patch.object(tasks_module.settings, "merkur_dry_run", False):
            try:
                _run_task(submit_to_merkur.run, invoice_id)
                assert False, "expected RuntimeError to propagate"
            except RuntimeError:
                pass

    assert _get_status(invoice_id) == InvoiceStatus.FAILED


def test_run_ocr_needs_review_on_null_extraction():
    invoice_id = _make_invoice(InvoiceStatus.RECEIVED, amount=None, date=None)

    with patch("workers.tasks.extract_rksv_from_image", return_value=None), \
         patch("services.rksv_parser.extract_qr_codes", return_value=[]), \
         patch("workers.tasks.pdf_to_text", new=AsyncMock(return_value="")), \
         patch("workers.tasks.parse_pharmacy_receipt") as mock_parse:
        mock_parse.return_value.date = None
        mock_parse.return_value.amount = None
        result = _run_task(run_ocr.run, invoice_id)

    assert result["status"] == "NEEDS_REVIEW"
    assert _get_status(invoice_id) == InvoiceStatus.NEEDS_REVIEW


def test_run_ocr_ready_for_merkur_on_success():
    from datetime import datetime

    invoice_id = _make_invoice(InvoiceStatus.RECEIVED, amount=None, date=None)

    class _Rksv:
        date = datetime(2026, 1, 15)
        amount = 9.99

    with patch("workers.tasks.extract_rksv_from_image", return_value=_Rksv()), \
         patch("services.rksv_parser.extract_qr_codes", return_value=["dummy"]):
        result = _run_task(run_ocr.run, invoice_id)

    assert result["status"] == "READY_FOR_MERKUR"
    assert _get_status(invoice_id) == InvoiceStatus.READY_FOR_MERKUR
