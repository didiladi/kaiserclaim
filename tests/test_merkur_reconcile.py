"""Merkur inbox reconciliation: stuck invoices, UNKNOWN re-evaluation, ambiguity."""
import asyncio
import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from models.domain import Invoice, InvoiceStatus, MerkurDocument, MerkurResultState, User
from tests.test_task_status_transitions import _TestSession  # also installs the NullPool engine
from workers.tasks import _process_scraped_doc

S = InvoiceStatus
R = MerkurResultState
DAY = datetime(2026, 5, 4, 12, tzinfo=timezone.utc)


def _run(coro):
    return asyncio.run(coro)


async def _user() -> uuid.UUID:
    async with _TestSession() as db:
        u = User(email=f"rec-{uuid.uuid4()}@example.invalid")
        db.add(u)
        await db.commit()
        return u.id


async def _invoice(user_id, status, amount=50.0, patient="Anna Test") -> uuid.UUID:
    async with _TestSession() as db:
        inv = Invoice(user_id=user_id, file_path="/tmp/x.pdf", status=status,
                      amount=amount, date=DAY, patient_name=patient)
        db.add(inv)
        await db.commit()
        return inv.id


def _meta(nr=None, state=R.REIMBURSED, amount=50.0, reimbursed=45.0, patient="Anna Test"):
    return {
        "geschaeftsfall_nr": nr or str(uuid.uuid4()),
        "result_state": state,
        "invoice_date": DAY,
        "invoice_amount": amount,
        "reimbursed_amount": reimbursed,
        "patient_name": patient,
    }


async def _status(inv_id) -> InvoiceStatus:
    async with _TestSession() as db:
        return (await db.get(Invoice, inv_id)).status


async def _doc(nr) -> MerkurDocument:
    async with _TestSession() as db:
        return (await db.execute(select(MerkurDocument).where(MerkurDocument.geschaeftsfall_nr == nr))).scalar_one()


def test_result_reimburses_submitted_invoice():
    uid = _run(_user())
    inv = _run(_invoice(uid, S.MERKUR_SUBMITTED))
    meta = _meta()
    assert _run(_process_scraped_doc(uid, meta)) == ("linked", True)
    assert _run(_status(inv)) == S.MERKUR_REIMBURSED
    assert _run(_doc(meta["geschaeftsfall_nr"])).invoice_id == inv


def test_result_rescues_failed_invoice_that_actually_went_through():
    """FAILED after the submit click: the Postfach result is the proof Merkur got it."""
    uid = _run(_user())
    inv = _run(_invoice(uid, S.FAILED))
    assert _run(_process_scraped_doc(uid, _meta()))[0] == "linked"
    assert _run(_status(inv)) == S.MERKUR_REIMBURSED


def test_result_rescues_invoice_stuck_in_submitting():
    uid = _run(_user())
    inv = _run(_invoice(uid, S.MERKUR_SUBMITTING))
    _run(_process_scraped_doc(uid, _meta(state=R.REJECTED, reimbursed=None)))
    assert _run(_status(inv)) == S.MERKUR_REJECTED


def test_rerun_of_same_document_is_a_duplicate():
    uid = _run(_user())
    _run(_invoice(uid, S.MERKUR_SUBMITTED))
    meta = _meta()
    _run(_process_scraped_doc(uid, meta))
    assert _run(_process_scraped_doc(uid, meta)) == ("duplicate", False)


def test_unmatched_document_is_linked_once_the_invoice_shows_up():
    uid = _run(_user())
    meta = _meta()
    assert _run(_process_scraped_doc(uid, meta)) == ("unmatched", True)

    inv = _run(_invoice(uid, S.MERKUR_SUBMITTED))
    assert _run(_process_scraped_doc(uid, meta)) == ("linked", False)  # same doc, not new
    assert _run(_status(inv)) == S.MERKUR_REIMBURSED


def test_unknown_result_is_reevaluated_on_next_sync():
    uid = _run(_user())
    inv = _run(_invoice(uid, S.MERKUR_SUBMITTED))
    nr = str(uuid.uuid4())

    _run(_process_scraped_doc(uid, _meta(nr=nr, state=R.UNKNOWN, reimbursed=None)))
    assert _run(_status(inv)) == S.MERKUR_SUBMITTED  # undecided, left alone

    _run(_process_scraped_doc(uid, _meta(nr=nr, state=R.REIMBURSED, reimbursed=44.0)))
    assert _run(_status(inv)) == S.MERKUR_REIMBURSED
    assert _run(_doc(nr)).reimbursed_amount == 44.0


def test_ambiguous_match_changes_nothing():
    uid = _run(_user())
    a = _run(_invoice(uid, S.MERKUR_SUBMITTED))
    b = _run(_invoice(uid, S.MERKUR_SUBMITTED))
    assert _run(_process_scraped_doc(uid, _meta())) == ("ambiguous", True)
    assert _run(_status(a)) == S.MERKUR_SUBMITTED
    assert _run(_status(b)) == S.MERKUR_SUBMITTED


def test_invoice_already_claimed_by_another_document_is_not_a_candidate():
    uid = _run(_user())
    first = _run(_invoice(uid, S.MERKUR_SUBMITTED))
    second = _run(_invoice(uid, S.MERKUR_SUBMITTED))
    meta1, meta2 = _meta(), _meta()

    # `first` is already claimed by an earlier document, so only `second` is a candidate.
    async def _claim():
        async with _TestSession() as db:
            db.add(MerkurDocument(
                user_id=uid, geschaeftsfall_nr=meta1["geschaeftsfall_nr"], title="t",
                result_state=R.REIMBURSED, invoice_id=first,
            ))
            await db.commit()
    _run(_claim())

    assert _run(_process_scraped_doc(uid, meta2)) == ("linked", True)
    assert _run(_status(second)) == S.MERKUR_REIMBURSED
    assert _run(_status(first)) == S.MERKUR_SUBMITTED


def test_missing_geschaeftsfall_is_skipped():
    uid = _run(_user())
    assert _run(_process_scraped_doc(uid, {"result_state": R.REIMBURSED})) == ("no_id", False)
