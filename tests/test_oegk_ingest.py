"""
Matching of ÖGK refund PDFs to invoices (services/oegk_ingest.py).

parse_oegk_pdf is patched with a synthetic result: no real PDF and no real
patient data. Every test uses a throwaway user, so leftover rows in the dev
database cannot influence the match counts.
"""
import uuid
from datetime import date, datetime, timezone
from unittest.mock import patch

import pytest
from sqlalchemy import select

from models.domain import FamilyMember, Invoice, InvoiceAttachment, InvoiceStatus, OegkDocument, User
from services.oegk_ingest import ingest_refund_pdf, invoice_matches
from services.oegk_result_parser import OegkResult
from tests.test_task_status_transitions import _TestSession

_SVNR = "1234010190"
_PDF = b"%PDF-1.4 synthetic"


def _result(**kw) -> OegkResult:
    base = dict(
        patient_name="Erika Muster BSc", patient_svnr=_SVNR, doctor_name="Dr. Max Beispiel",
        invoice_amount=350.00, reimbursed_amount=62.73,
        service_from=date(2026, 4, 27), service_to=date(2026, 4, 27), payout_date=date(2026, 4, 28),
    )
    base.update(kw)
    return OegkResult(**base)


async def _user() -> uuid.UUID:
    async with _TestSession() as db:
        user = User(email=f"ingest-{uuid.uuid4()}@example.invalid")
        db.add(user)
        await db.commit()
        return user.id


async def _member(user_id, svnr=None) -> uuid.UUID:
    async with _TestSession() as db:
        m = FamilyMember(user_id=user_id, member_key=f"m{uuid.uuid4().hex[:8]}", name="Erika Muster",
                         color="#000000", initials="EM", svnr=svnr)
        db.add(m)
        await db.commit()
        return m.id


async def _invoice(user_id, *, status=InvoiceStatus.OEGK_SUBMITTED, amount=350.00,
                   when=datetime(2026, 4, 27, 10, tzinfo=timezone.utc), patient="Erika Muster",
                   member_id=None) -> uuid.UUID:
    async with _TestSession() as db:
        inv = Invoice(user_id=user_id, file_path="/tmp/kaiserclaim-test-storage/fixture.pdf",
                      status=status, amount=amount, date=when, patient_name=patient,
                      family_member_id=member_id)
        db.add(inv)
        await db.commit()
        return inv.id


async def _ingest(user_id, tmp_path, result=None):
    with patch("services.oegk_ingest.parse_oegk_pdf", return_value=result or _result()):
        async with _TestSession() as db:
            return await ingest_refund_pdf(db, user_id, _PDF, str(tmp_path))


async def _status(invoice_id):
    async with _TestSession() as db:
        return (await db.get(Invoice, invoice_id)).status


@pytest.mark.asyncio
async def test_links_invoice_attaches_pdf_and_advances(tmp_path):
    user = await _user()
    invoice_id = await _invoice(user)

    r = await _ingest(user, tmp_path)

    assert r.outcome == "linked" and r.invoice_id == invoice_id and r.is_new
    assert await _status(invoice_id) == InvoiceStatus.READY_FOR_MERKUR
    async with _TestSession() as db:
        att = (await db.execute(select(InvoiceAttachment).where(InvoiceAttachment.invoice_id == invoice_id))).scalar_one()
        doc = (await db.execute(select(OegkDocument).where(OegkDocument.user_id == user))).scalar_one()
    assert att.kind == "oegk_refund" and att.file_path == doc.file_path
    assert (tmp_path / str(user) / "oegk_refunds" / f"{doc.dedupe_key[:16]}.pdf").read_bytes() == _PDF


@pytest.mark.asyncio
async def test_same_pdf_twice_is_duplicate(tmp_path):
    user = await _user()
    invoice_id = await _invoice(user)
    await _ingest(user, tmp_path)

    r = await _ingest(user, tmp_path)

    assert r.outcome == "duplicate" and r.invoice_id == invoice_id and not r.is_new
    async with _TestSession() as db:
        n = len((await db.execute(select(InvoiceAttachment).where(InvoiceAttachment.invoice_id == invoice_id))).all())
    assert n == 1


@pytest.mark.asyncio
async def test_unmatched_is_stored_then_linked_when_invoice_appears(tmp_path):
    user = await _user()

    first = await _ingest(user, tmp_path)
    again = await _ingest(user, tmp_path)
    assert (first.outcome, first.is_new) == ("unmatched", True)
    assert (again.outcome, again.is_new) == ("unmatched", False)  # no repeat notification

    invoice_id = await _invoice(user)  # the invoice shows up later
    later = await _ingest(user, tmp_path)

    assert later.outcome == "linked" and later.invoice_id == invoice_id
    async with _TestSession() as db:
        docs = (await db.execute(select(OegkDocument).where(OegkDocument.user_id == user))).all()
    assert len(docs) == 1


@pytest.mark.asyncio
async def test_two_identical_candidates_are_ambiguous_and_untouched(tmp_path):
    user = await _user()
    a = await _invoice(user)
    b = await _invoice(user)

    r = await _ingest(user, tmp_path)

    assert r.outcome == "ambiguous" and r.invoice_id is None
    assert await _status(a) == await _status(b) == InvoiceStatus.OEGK_SUBMITTED


@pytest.mark.asyncio
async def test_other_users_invoice_is_never_matched(tmp_path):
    user, other = await _user(), await _user()
    theirs = await _invoice(other)

    r = await _ingest(user, tmp_path)

    assert r.outcome == "unmatched"
    assert await _status(theirs) == InvoiceStatus.OEGK_SUBMITTED


@pytest.mark.asyncio
async def test_svnr_decides_between_patients(tmp_path):
    user = await _user()
    wife = await _member(user, svnr="9999010185")
    me = await _member(user, svnr=_SVNR)
    wifes_invoice = await _invoice(user, member_id=wife)
    my_invoice = await _invoice(user, member_id=me)  # identical date and amount

    r = await _ingest(user, tmp_path)

    assert r.outcome == "linked" and r.invoice_id == my_invoice
    assert await _status(wifes_invoice) == InvoiceStatus.OEGK_SUBMITTED


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [InvoiceStatus.READY_FOR_OEGK, InvoiceStatus.OEGK_SUBMITTING, InvoiceStatus.FAILED])
async def test_rescues_invoices_submitted_by_hand(tmp_path, status):
    user = await _user()
    invoice_id = await _invoice(user, status=status)

    r = await _ingest(user, tmp_path)

    assert r.outcome == "linked"
    assert await _status(invoice_id) == InvoiceStatus.READY_FOR_MERKUR


@pytest.mark.asyncio
async def test_invoice_already_completed_is_not_a_candidate(tmp_path):
    user = await _user()
    await _invoice(user, status=InvoiceStatus.COMPLETED)

    assert (await _ingest(user, tmp_path)).outcome == "unmatched"


@pytest.mark.asyncio
async def test_not_a_refund(tmp_path):
    user = await _user()
    with patch("services.oegk_ingest.parse_oegk_pdf", return_value=None):
        async with _TestSession() as db:
            r = await ingest_refund_pdf(db, user, b"junk", str(tmp_path))
    assert r.outcome == "not_a_refund"
    assert not list(tmp_path.rglob("*.pdf"))  # nothing stored


# --- invoice_matches: the rules in isolation ---------------------------------

def _inv(**kw) -> Invoice:
    base = dict(amount=350.00, date=datetime(2026, 4, 27, 10, tzinfo=timezone.utc), patient_name="Erika Muster")
    base.update(kw)
    return Invoice(**base)


def test_match_uses_vienna_day_not_utc():
    # 22:30 UTC on 26 Apr is already 27 Apr (00:30) in Vienna.
    assert invoice_matches(_inv(date=datetime(2026, 4, 26, 22, 30, tzinfo=timezone.utc)), None, _result())
    assert not invoice_matches(_inv(date=datetime(2026, 4, 26, 21, 30, tzinfo=timezone.utc)), None, _result())


def test_match_date_range():
    r = _result(service_from=date(2026, 4, 27), service_to=date(2026, 4, 29))
    assert invoice_matches(_inv(date=datetime(2026, 4, 28, 10, tzinfo=timezone.utc)), None, r)
    assert not invoice_matches(_inv(date=datetime(2026, 4, 30, 10, tzinfo=timezone.utc)), None, r)


def test_match_amount_tolerance_one_cent():
    assert invoice_matches(_inv(amount=350.01), None, _result())
    assert not invoice_matches(_inv(amount=350.05), None, _result())


def test_match_needs_date_and_amount():
    assert not invoice_matches(_inv(date=None), None, _result())
    assert not invoice_matches(_inv(amount=None), None, _result())


def test_match_name_fallback_without_svnr():
    assert invoice_matches(_inv(patient_name="erika muster"), None, _result())
    assert not invoice_matches(_inv(patient_name="Hans Anders"), None, _result())
    assert invoice_matches(_inv(patient_name=None), None, _result())  # no name info: date + amount decide


def test_match_svnr_overrides_name():
    assert invoice_matches(_inv(patient_name="Hans Anders"), _SVNR, _result())
    assert not invoice_matches(_inv(), "9999010185", _result())
