"""Dashboard / stats numbers: real reimbursements, estimates, date bucketing."""
import uuid
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from models.domain import Invoice, InvoiceStatus, MerkurDocument, MerkurResultState, User
from tests.conftest import _TEST_DB_URL

S = InvoiceStatus
_VIENNA = ZoneInfo("Europe/Vienna")


async def _seed(rows):
    """rows: dicts with status/amount/date and optional reimbursed (creates a MerkurDocument).
    Returns the fresh user's id."""
    engine = create_async_engine(_TEST_DB_URL)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as db:
            user = User(email=f"stats-{uuid.uuid4()}@example.invalid")
            db.add(user)
            await db.flush()
            for r in rows:
                inv = Invoice(
                    user_id=user.id,
                    file_path="/tmp/x.pdf",
                    status=r["status"],
                    amount=r["amount"],
                    date=r.get("date"),
                )
                db.add(inv)
                await db.flush()
                if "reimbursed" in r:
                    db.add(MerkurDocument(
                        user_id=user.id,
                        geschaeftsfall_nr=str(uuid.uuid4()),
                        title="t",
                        result_state=MerkurResultState.REIMBURSED,
                        reimbursed_amount=r["reimbursed"],
                        invoice_id=inv.id,
                    ))
            await db.commit()
            return user.id
    finally:
        await engine.dispose()


def _d(y, m, day, hour=12):
    return datetime(y, m, day, hour, tzinfo=_VIENNA)


async def _summary(client, user_id, year=2026):
    r = await client.get(f"/api/v1/dashboard/summary?user_id={user_id}&year={year}")
    assert r.status_code == 200, r.text
    return r.json()


@pytest.mark.asyncio
async def test_merkur_reimbursed_counts_with_real_amount(client):
    """Regression: invoices finalize to MERKUR_REIMBURSED, never COMPLETED."""
    uid = await _seed([{"status": S.MERKUR_REIMBURSED, "amount": 100.0, "date": _d(2026, 3, 1), "reimbursed": 91.5}])
    s = await _summary(client, uid)
    assert s["total_reimbursed"] == 91.5
    assert s["reimbursed_confirmed"] == 91.5
    assert s["reimbursed_estimated"] == 0
    assert s["eigenanteil"] == 8.5
    assert s["in_progress_count"] == 0


@pytest.mark.asyncio
async def test_missing_merkur_document_falls_back_to_labelled_estimate(client):
    uid = await _seed([{"status": S.COMPLETED, "amount": 100.0, "date": _d(2026, 3, 1)}])
    s = await _summary(client, uid)
    assert s["reimbursed_estimated"] == 82.0
    assert s["reimbursed_confirmed"] == 0
    assert s["total_reimbursed"] == 82.0


@pytest.mark.asyncio
async def test_rejected_is_settled_with_no_reimbursement(client):
    uid = await _seed([{"status": S.MERKUR_REJECTED, "amount": 40.0, "date": _d(2026, 3, 1)}])
    s = await _summary(client, uid)
    assert s["total_reimbursed"] == 0
    assert s["eigenanteil"] == 40.0
    assert s["in_progress_count"] == 0


@pytest.mark.asyncio
async def test_pending_is_not_counted_as_eigenanteil(client):
    uid = await _seed([
        {"status": S.MERKUR_SUBMITTED, "amount": 60.0, "date": _d(2026, 3, 1)},
        {"status": S.NEEDS_REVIEW, "amount": 10.0, "date": _d(2026, 3, 2)},
        {"status": S.FAILED, "amount": 5.0, "date": _d(2026, 3, 3)},
    ])
    s = await _summary(client, uid)
    assert s["total_paid"] == 75.0
    assert s["eigenanteil"] == 0
    assert s["pending_amount"] == 70.0
    assert s["in_progress_count"] == 2  # submitted + needs review; FAILED is not "in progress"
    assert s["needs_attention_count"] == 2  # needs review + failed


@pytest.mark.asyncio
async def test_bucketed_by_invoice_date_not_upload_date(client):
    # Uploaded now (created_at), but dated 2025: belongs to 2025.
    uid = await _seed([{"status": S.MERKUR_SUBMITTED, "amount": 30.0, "date": _d(2025, 6, 1)}])
    assert (await _summary(client, uid, 2025))["total_paid"] == 30.0
    assert (await _summary(client, uid, 2026))["total_paid"] == 0


@pytest.mark.asyncio
async def test_year_boundary_uses_vienna_time(client):
    # 23:30 UTC on 31 Dec is 00:30 on 1 Jan in Vienna.
    uid = await _seed([{
        "status": S.MERKUR_SUBMITTED, "amount": 20.0,
        "date": datetime(2025, 12, 31, 23, 30, tzinfo=timezone.utc),
    }])
    assert (await _summary(client, uid, 2026))["total_paid"] == 20.0
    assert (await _summary(client, uid, 2025))["total_paid"] == 0


@pytest.mark.asyncio
async def test_year_defaults_to_current_year(client):
    uid = await _seed([])
    r = await client.get(f"/api/v1/dashboard/summary?user_id={uid}")
    assert r.json()["year"] == datetime.now(_VIENNA).year


@pytest.mark.asyncio
async def test_yearly_and_monthly_use_same_roll_up(client):
    uid = await _seed([
        {"status": S.MERKUR_REIMBURSED, "amount": 100.0, "date": _d(2026, 3, 1), "reimbursed": 90.0},
        {"status": S.MERKUR_SUBMITTED, "amount": 50.0, "date": _d(2026, 4, 1)},
    ])
    yearly = (await client.get(f"/api/v1/stats/yearly?user_id={uid}")).json()
    assert yearly == [{
        "year": 2026, "total_paid": 150.0, "total_reimbursed": 90.0,
        "reimbursed_confirmed": 90.0, "reimbursed_estimated": 0.0,
        "eigenanteil": 10.0, "pending_amount": 50.0,
        "in_progress_count": 1, "needs_attention_count": 0,
    }]
    monthly = (await client.get(f"/api/v1/stats/monthly?user_id={uid}&year=2026")).json()
    assert monthly[2]["total"] == 100.0 and monthly[3]["total"] == 50.0
