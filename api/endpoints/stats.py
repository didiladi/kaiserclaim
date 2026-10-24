"""
Dashboard summary and statistics aggregation endpoints.

All monetary figures are in EUR.

Reimbursement has two sources that add up (Merkur's statement deducts what the
Sozialversicherung paid):
- ÖGK: the real refund of the matched OegkDocument, counted as soon as the PDF is
  linked, even while the invoice still waits for Merkur. Never estimated.
- Merkur: counted once the invoice is MERKUR_REIMBURSED (or COMPLETED), from the
  matched MerkurDocument ("confirmed"). Without one it falls back to an estimate
  (_REIMBURSEMENT_RATE of the invoice minus the ÖGK part), reported separately as
  "estimated" so the UI can label it.

"Claimed" is an invoice that was submitted to ÖGK or Merkur; "claimed open" is the
part of it not yet decided. Invoices are bucketed by their own date (created_at as
fallback), in Vienna local time.
"""
from datetime import date, datetime, timezone, timedelta
from typing import Any, Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.dependencies import get_current_user
from core.database import get_db
from models.domain import BenefitKind, BenefitRule, BenefitUsage, FamilyMember, InsuredPerson, Invoice, InvoiceStatus, ResetPeriod, Tariff, User
from schemas.payload import _derive_pipeline

router = APIRouter(tags=["stats"])

_REIMBURSEMENT_RATE = 0.82
_VIENNA = ZoneInfo("Europe/Vienna")

_REIMBURSED_STATUSES = {InvoiceStatus.MERKUR_REIMBURSED, InvoiceStatus.COMPLETED}
# Nothing more will happen to these without a human.
_SETTLED_STATUSES = _REIMBURSED_STATUSES | {InvoiceStatus.MERKUR_REJECTED}
_NEEDS_ATTENTION_STATUSES = {InvoiceStatus.FAILED, InvoiceStatus.NEEDS_REVIEW}
# Submitted to ÖGK or Merkur (an invoice with a linked ÖGK refund counts too).
_CLAIMED_STATUSES = {
    InvoiceStatus.OEGK_SUBMITTING, InvoiceStatus.OEGK_SUBMITTED, InvoiceStatus.OEGK_REFUNDED,
    InvoiceStatus.MERKUR_SUBMITTING, InvoiceStatus.MERKUR_SUBMITTED,
} | _SETTLED_STATUSES


def _current_year() -> int:
    return datetime.now(_VIENNA).year


def _invoice_when(invoice: Invoice) -> datetime:
    """The invoice's own date, falling back to when it was uploaded (Vienna time)."""
    return (invoice.date or invoice.created_at).astimezone(_VIENNA)


def _oegk_refund(invoice: Invoice) -> float:
    """What ÖGK paid for this invoice (confirmed by its refund PDF), else 0."""
    doc = invoice.oegk_document
    return float(doc.reimbursed_amount) if doc is not None and doc.reimbursed_amount is not None else 0.0


def _merkur_refund(invoice: Invoice, oegk: float) -> tuple[float, bool]:
    """(amount, is_estimate). Zero while Merkur has not decided."""
    if invoice.status not in _REIMBURSED_STATUSES:
        return 0.0, False
    doc = invoice.merkur_document
    if doc is not None and doc.reimbursed_amount is not None:
        return float(doc.reimbursed_amount), False
    return max(float(invoice.amount or 0) * _REIMBURSEMENT_RATE - oegk, 0.0), True


def _is_claimed(invoice: Invoice) -> bool:
    return invoice.status in _CLAIMED_STATUSES or invoice.oegk_document is not None


def _totals(invoices: list[Invoice]) -> dict[str, float | int]:
    """Money roll-up shared by every endpoint."""
    paid = oegk_total = merkur_confirmed = merkur_estimated = 0.0
    settled_paid = settled_refunded = pending = 0.0
    claimed = claimed_open = not_claimed = 0.0
    in_progress = attention = 0
    for inv in invoices:
        amt = float(inv.amount or 0)
        paid += amt
        oegk = _oegk_refund(inv)
        merkur, is_estimate = _merkur_refund(inv, oegk)
        oegk_total += oegk
        if is_estimate:
            merkur_estimated += merkur
        else:
            merkur_confirmed += merkur

        settled = inv.status in _SETTLED_STATUSES
        if settled:
            settled_paid += amt
            settled_refunded += oegk + merkur
        elif inv.status != InvoiceStatus.FAILED:
            pending += amt
            in_progress += 1

        if _is_claimed(inv):
            claimed += amt
            if not settled:
                claimed_open += amt
        elif not settled and inv.status != InvoiceStatus.FAILED:
            not_claimed += amt

        if inv.status in _NEEDS_ATTENTION_STATUSES:
            attention += 1
    return {
        "total_paid": round(paid, 2),
        "total_reimbursed": round(oegk_total + merkur_confirmed + merkur_estimated, 2),
        "reimbursed_confirmed": round(oegk_total + merkur_confirmed, 2),
        "reimbursed_estimated": round(merkur_estimated, 2),
        "oegk_refunded": round(oegk_total, 2),
        "merkur_refunded": round(merkur_confirmed, 2),
        # Out-of-pocket only for invoices that are decided; the rest is still pending.
        "eigenanteil": round(settled_paid - settled_refunded, 2),
        "pending_amount": round(pending, 2),
        # Invoice totals: submitted to ÖGK/Merkur, of which still undecided, and not yet submitted.
        "claimed_amount": round(claimed, 2),
        "claimed_open_amount": round(claimed_open, 2),
        "not_yet_claimed_amount": round(not_claimed, 2),
        "in_progress_count": in_progress,
        "needs_attention_count": attention,
    }


async def _load_invoices(
    db: AsyncSession, user_id, year: int | None, member_id=None,
    pipeline: Literal["standard", "pharmacy"] | None = None,
) -> list[Invoice]:
    stmt = (
        select(Invoice)
        .where(Invoice.user_id == user_id)
        .options(selectinload(Invoice.merkur_document), selectinload(Invoice.oegk_document))
    )
    if member_id:
        stmt = stmt.where(Invoice.family_member_id == member_id)
    invoices = (await db.execute(stmt)).scalars().all()
    if pipeline:
        invoices = [i for i in invoices if _derive_pipeline(i.category) == pipeline]
    if year is None:
        return list(invoices)
    return [i for i in invoices if _invoice_when(i).year == year]

_MONTH_NAMES = ["Jan", "Feb", "Mär", "Apr", "Mai", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"]


async def _resolve_member_id(db: AsyncSession, user_id, member_key: str | None):
    if not member_key:
        return None
    result = await db.execute(
        select(FamilyMember.id).where(
            FamilyMember.user_id == user_id,
            FamilyMember.member_key == member_key,
        )
    )
    return result.scalar_one_or_none()


@router.get("/dashboard/summary")
async def dashboard_summary(
    year: int = Query(default_factory=_current_year),
    member_key: str | None = Query(default=None),
    pipeline: Literal["standard", "pharmacy"] | None = Query(
        default=None, description="standard = doctors and other ÖGK-first invoices, pharmacy = Merkur only"
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    member_id = await _resolve_member_id(db, current_user.id, member_key)
    invoices = await _load_invoices(db, current_user.id, year, member_id, pipeline)
    totals = _totals(invoices)

    # Benefit alerts: find rules where usage >= 75% of limit (nearly used up)
    benefit_alerts = []
    all_rules_result = await db.execute(
        select(BenefitRule).join(BenefitRule.contract).where(
            BenefitRule.contract.has(user_id=current_user.id)
        )
    )
    all_rules = all_rules_result.scalars().all()
    for rule in all_rules:
        used_result = await db.execute(
            select(func.coalesce(func.sum(BenefitUsage.amount_used), 0)).where(
                BenefitUsage.benefit_rule_id == rule.id
            )
        )
        used = used_result.scalar() or 0
        pct = (used / rule.limit_amount * 100) if rule.limit_amount else 0
        if pct >= 75:
            benefit_alerts.append({
                "benefit_name": rule.benefit_name,
                "percent_used": round(pct, 1),
                "used": used,
                "limit": rule.limit_amount,
            })

    # Unused alerts: find yearly BUDGET/PROGRAM benefits that are under-used
    # and whose reset date is within the lead window (8 weeks = 56 days).
    unused_alerts = await _compute_unused_alerts(db, current_user.id, all_rules)

    return {
        "year": year,
        **totals,
        "benefit_alerts": benefit_alerts,
        "unused_alerts": unused_alerts,
    }


_YEARLY_RESET_PERIODS = {ResetPeriod.CALENDAR_YEAR, ResetPeriod.ONCE_PER_YEAR, ResetPeriod.INSURANCE_YEAR}
_UNUSED_LEAD_DAYS = 56  # 8 weeks before reset → start showing reminders


async def _compute_unused_alerts(db, user_id, all_rules: list) -> list[dict]:
    """
    For each yearly BUDGET or PROGRAM benefit: if it's unused (or < 30% used)
    and the next reset is within _UNUSED_LEAD_DAYS days, surface a reminder.
    """
    today = date.today()
    current_year = today.year
    alerts = []

    # Pre-load insured person names keyed by contract_id → tariff_id → person name
    person_names: dict[str, str] = {}  # tariff_id → person full_name
    persons_result = await db.execute(
        select(InsuredPerson, Tariff)
        .join(Tariff, Tariff.insured_person_id == InsuredPerson.id)
    )
    for person, tariff in persons_result:
        person_names[str(tariff.id)] = person.full_name

    for rule in all_rules:
        # Only yearly/once-per-year BUDGET or PROGRAM benefits
        if rule.reset_period not in _YEARLY_RESET_PERIODS:
            continue
        if rule.benefit_kind not in (BenefitKind.BUDGET, BenefitKind.PROGRAM, None):
            continue
        # Skip DEDUCTIBLE
        if rule.benefit_kind == BenefitKind.DEDUCTIBLE:
            continue

        # Compute reset date for current period
        if rule.reset_period in (ResetPeriod.CALENDAR_YEAR, ResetPeriod.ONCE_PER_YEAR):
            reset_date = date(current_year, 12, 31)
        elif rule.reset_period == ResetPeriod.INSURANCE_YEAR:
            # Default: October 1 (common for Merkur)
            candidate = date(current_year, 10, 1)
            reset_date = candidate if candidate >= today else date(current_year + 1, 10, 1)
        else:
            continue

        days_until_reset = (reset_date - today).days
        if days_until_reset < 0 or days_until_reset > _UNUSED_LEAD_DAYS:
            continue

        # Compute usage for this rule
        used_result = await db.execute(
            select(func.coalesce(func.sum(BenefitUsage.amount_used), 0.0)).where(
                BenefitUsage.benefit_rule_id == rule.id
            )
        )
        used = float(used_result.scalar() or 0.0)

        if rule.benefit_kind == BenefitKind.PROGRAM:
            # PROGRAM: alert if never used
            if used > 0:
                continue
            pct_unused = 100.0
        else:
            # BUDGET: alert if < 30% used
            if not rule.limit_amount or rule.limit_amount <= 0:
                continue
            pct_used = used / rule.limit_amount * 100
            if pct_used >= 30:
                continue
            pct_unused = round(100.0 - pct_used, 1)

        person_name = person_names.get(str(rule.tariff_id)) if rule.tariff_id else None
        alerts.append({
            "benefit_name": rule.benefit_name,
            "person_name": person_name,
            "pct_unused": pct_unused,
            "limit": rule.limit_amount,
            "days_until_reset": days_until_reset,
            "reset_date": reset_date.isoformat(),
        })

    return alerts


@router.get("/stats/monthly")
async def stats_monthly(
    year: int = Query(default_factory=_current_year),
    member_key: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[dict[str, Any]]:
    member_id = await _resolve_member_id(db, current_user.id, member_key)
    invoices = await _load_invoices(db, current_user.id, year, member_id)

    # Fetch all family members for by_member breakdown
    members_result = await db.execute(
        select(FamilyMember).where(FamilyMember.user_id == current_user.id)
    )
    members = {m.id: m.member_key for m in members_result.scalars().all()}

    months: dict[int, dict] = {}
    for invoice in invoices:
        month_num = _invoice_when(invoice).month
        if month_num not in months:
            months[month_num] = {"month": _MONTH_NAMES[month_num - 1], "total": 0.0, "by_member": {}}
        amt = invoice.amount or 0
        months[month_num]["total"] += amt
        mk = members.get(invoice.family_member_id, "unknown") if invoice.family_member_id else "unknown"
        months[month_num]["by_member"][mk] = months[month_num]["by_member"].get(mk, 0) + amt

    # Return all 12 months, zero-filling missing ones
    return [
        {
            "month": _MONTH_NAMES[i],
            "total": round(months.get(i + 1, {}).get("total", 0), 2),
            "by_member": months.get(i + 1, {}).get("by_member", {}),
        }
        for i in range(12)
    ]


@router.get("/stats/yearly")
async def stats_yearly(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[dict[str, Any]]:
    invoices = await _load_invoices(db, current_user.id, None)

    by_year: dict[int, list[Invoice]] = {}
    for invoice in invoices:
        by_year.setdefault(_invoice_when(invoice).year, []).append(invoice)

    return [{"year": year, **_totals(items)} for year, items in sorted(by_year.items())]


@router.get("/stats/members")
async def stats_members(
    year: int = Query(default_factory=_current_year),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[dict[str, Any]]:
    members_result = await db.execute(
        select(FamilyMember).where(FamilyMember.user_id == current_user.id)
    )
    members = members_result.scalars().all()

    all_invoices = await _load_invoices(db, current_user.id, year)

    family_total = sum(i.amount or 0 for i in all_invoices)

    output = []
    for member in members:
        member_invoices = [i for i in all_invoices if i.family_member_id == member.id]
        totals = _totals(member_invoices)
        total_paid = totals["total_paid"]

        # Category breakdown
        categories: dict[str, float] = {}
        for inv in member_invoices:
            cat = inv.category or "Sonstiges"
            categories[cat] = categories.get(cat, 0) + (inv.amount or 0)

        output.append({
            "member_key": member.member_key,
            "name": member.name,
            "color": member.color,
            "initials": member.initials,
            "invoice_count": len(member_invoices),
            **totals,
            "share_pct": round(total_paid / family_total * 100, 1) if family_total else 0,
            "categories": [
                {"name": k, "amount": round(v, 2)}
                for k, v in sorted(categories.items(), key=lambda x: -x[1])
            ],
        })

    return output
