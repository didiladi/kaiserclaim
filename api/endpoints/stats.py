"""
Dashboard summary and statistics aggregation endpoints.

All monetary figures are in EUR. The reimbursement rate of 82% is applied to
COMPLETED invoices to compute total_reimbursed and eigenanteil, matching the
design spec's financial model.
"""
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import extract, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_current_user
from core.database import get_db
from models.domain import BenefitRule, BenefitUsage, FamilyMember, Invoice, InvoiceStatus, User

router = APIRouter(tags=["stats"])

_REIMBURSEMENT_RATE = 0.82

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
    year: int = Query(default=2026),
    member_key: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    member_id = await _resolve_member_id(db, current_user.id, member_key)

    stmt = select(Invoice).where(
        Invoice.user_id == current_user.id,
        extract("year", Invoice.created_at) == year,
    )
    if member_id:
        stmt = stmt.where(Invoice.family_member_id == member_id)

    result = await db.execute(stmt)
    invoices = result.scalars().all()

    total_paid = sum(i.amount or 0 for i in invoices)
    completed = [i for i in invoices if i.status == InvoiceStatus.COMPLETED]
    total_reimbursed = sum(i.amount or 0 for i in completed) * _REIMBURSEMENT_RATE
    in_progress_count = sum(1 for i in invoices if i.status != InvoiceStatus.COMPLETED)
    eigenanteil = total_paid - total_reimbursed

    # Benefit alerts: find rules where usage >= 75% of limit
    benefit_alerts = []
    all_rules_result = await db.execute(
        select(BenefitRule).join(BenefitRule.contract).where(
            BenefitRule.contract.has(user_id=current_user.id)
        )
    )
    for rule in all_rules_result.scalars().all():
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

    return {
        "year": year,
        "total_paid": round(total_paid, 2),
        "total_reimbursed": round(total_reimbursed, 2),
        "in_progress_count": in_progress_count,
        "eigenanteil": round(eigenanteil, 2),
        "benefit_alerts": benefit_alerts,
    }


@router.get("/stats/monthly")
async def stats_monthly(
    year: int = Query(default=2026),
    member_key: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[dict[str, Any]]:
    member_id = await _resolve_member_id(db, current_user.id, member_key)

    stmt = select(Invoice).where(
        Invoice.user_id == current_user.id,
        extract("year", Invoice.created_at) == year,
    )
    if member_id:
        stmt = stmt.where(Invoice.family_member_id == member_id)

    result = await db.execute(stmt)
    invoices = result.scalars().all()

    # Fetch all family members for by_member breakdown
    members_result = await db.execute(
        select(FamilyMember).where(FamilyMember.user_id == current_user.id)
    )
    members = {m.id: m.member_key for m in members_result.scalars().all()}

    months: dict[int, dict] = {}
    for invoice in invoices:
        month_num = invoice.created_at.month
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
    result = await db.execute(
        select(Invoice).where(Invoice.user_id == current_user.id)
    )
    invoices = result.scalars().all()

    by_year: dict[int, dict] = {}
    for invoice in invoices:
        year = invoice.created_at.year
        if year not in by_year:
            by_year[year] = {"year": year, "total": 0.0, "completed": 0.0}
        amt = invoice.amount or 0
        by_year[year]["total"] += amt
        if invoice.status == InvoiceStatus.COMPLETED:
            by_year[year]["completed"] += amt

    return [
        {
            "year": year,
            "total_paid": round(data["total"], 2),
            "total_reimbursed": round(data["completed"] * _REIMBURSEMENT_RATE, 2),
            "eigenanteil": round(data["total"] - data["completed"] * _REIMBURSEMENT_RATE, 2),
        }
        for year, data in sorted(by_year.items())
    ]


@router.get("/stats/members")
async def stats_members(
    year: int = Query(default=2026),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[dict[str, Any]]:
    members_result = await db.execute(
        select(FamilyMember).where(FamilyMember.user_id == current_user.id)
    )
    members = members_result.scalars().all()

    invoices_result = await db.execute(
        select(Invoice).where(
            Invoice.user_id == current_user.id,
            extract("year", Invoice.created_at) == year,
        )
    )
    all_invoices = invoices_result.scalars().all()

    family_total = sum(i.amount or 0 for i in all_invoices)

    output = []
    for member in members:
        member_invoices = [i for i in all_invoices if i.family_member_id == member.id]
        total_paid = sum(i.amount or 0 for i in member_invoices)
        completed_amt = sum(i.amount or 0 for i in member_invoices if i.status == InvoiceStatus.COMPLETED)
        total_reimbursed = completed_amt * _REIMBURSEMENT_RATE
        eigenanteil = total_paid - total_reimbursed

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
            "total_paid": round(total_paid, 2),
            "total_reimbursed": round(total_reimbursed, 2),
            "eigenanteil": round(eigenanteil, 2),
            "share_pct": round(total_paid / family_total * 100, 1) if family_total else 0,
            "categories": [
                {"name": k, "amount": round(v, 2)}
                for k, v in sorted(categories.items(), key=lambda x: -x[1])
            ],
        })

    return output
