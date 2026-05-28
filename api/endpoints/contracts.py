import shutil
import tempfile
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.dependencies import get_current_user
from core.config import get_settings
from core.database import get_db
from models.domain import (
    BenefitKind,
    BenefitRule,
    BenefitUsage,
    FamilyMember,
    InsuranceContract,
    InsuredPerson,
    ResetPeriod,
    Tariff,
    User,
)
from schemas.payload import (
    BenefitRuleCreate,
    BenefitRuleDetailRead,
    BenefitRuleRead,
    BenefitRuleWithRemaining,
    ContractCoverageRead,
    ContractCreate,
    ContractRead,
    InsuredPersonRead,
    TariffRead,
)
from services.llm_auditor import parse_contract, parse_contract_full
from services.ocr_engine import pdf_to_text, pdf_to_text_native

settings = get_settings()
router = APIRouter(prefix="/contracts", tags=["contracts"])


@router.get("/", response_model=list[ContractRead])
async def list_contracts(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(InsuranceContract)
        .where(InsuranceContract.user_id == current_user.id)
        .order_by(InsuranceContract.created_at.desc())
    )
    return result.scalars().all()


@router.post("/", response_model=ContractRead, status_code=status.HTTP_201_CREATED)
async def create_contract(
    payload: ContractCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    contract = InsuranceContract(user_id=current_user.id, **payload.model_dump())
    db.add(contract)
    await db.commit()
    await db.refresh(contract)
    return contract


@router.post("/{contract_id}/parse-pdf", response_model=ContractCoverageRead)
async def parse_contract_pdf(
    contract_id: UUID,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Upload the insurance contract PDF. Runs OCR then sends text to Gemini
    to extract per-person BenefitRules. Existing persons/tariffs/rules for
    this contract are replaced.
    """
    contract = await db.get(InsuranceContract, contract_id)
    _assert_owned(contract, current_user.id)

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name

    # Use native pdfminer extraction (instant for digital PDFs like Polizzen).
    # Falls back to full OCR automatically if the PDF is a scanned image.
    text = await pdf_to_text_native(tmp_path)
    Path(tmp_path).unlink(missing_ok=True)

    extraction = await parse_contract_full(text)

    # Load all family members for first-name matching
    members_result = await db.execute(
        select(FamilyMember).where(FamilyMember.user_id == current_user.id)
    )
    family_members = members_result.scalars().all()

    # Replace existing insured persons (cascades to tariffs and per-person benefit_rules)
    existing_persons = await db.execute(
        select(InsuredPerson).where(InsuredPerson.contract_id == contract_id)
    )
    for person in existing_persons.scalars().all():
        await db.delete(person)

    # Also replace legacy contract-level benefit_rules
    existing_rules = await db.execute(
        select(BenefitRule).where(
            BenefitRule.contract_id == contract_id,
            BenefitRule.tariff_id.is_(None),
        )
    )
    for rule in existing_rules.scalars().all():
        await db.delete(rule)

    await db.flush()

    # Insert new data
    new_persons = []
    for person_data in extraction.get("persons", []):
        family_member_id = _match_family_member(person_data.get("full_name", ""), family_members)
        birth_date = _parse_date(person_data.get("birth_date"))

        person = InsuredPerson(
            contract_id=contract_id,
            family_member_id=family_member_id,
            full_name=person_data.get("full_name", ""),
            kd_nr=person_data.get("kd_nr"),
            birth_date=birth_date,
        )
        db.add(person)
        await db.flush()  # get person.id

        for tariff_data in person_data.get("tariffs", []):
            tariff = Tariff(
                insured_person_id=person.id,
                code=tariff_data.get("code", ""),
                name=tariff_data.get("name"),
                description_raw=tariff_data.get("description_raw"),
            )
            db.add(tariff)
            await db.flush()  # get tariff.id

            for benefit_data in tariff_data.get("benefits", []):
                rule = BenefitRule(
                    contract_id=contract_id,
                    tariff_id=tariff.id,
                    benefit_name=benefit_data.get("benefit_name", ""),
                    benefit_kind=_coerce_enum(BenefitKind, benefit_data.get("benefit_kind")),
                    limit_amount=_coerce_float(benefit_data.get("limit_amount")),
                    reimbursement_pct=_coerce_float(benefit_data.get("reimbursement_pct")),
                    reset_period=_coerce_enum(ResetPeriod, benefit_data.get("reset_period")),
                    category=benefit_data.get("category"),
                    notes=benefit_data.get("notes"),
                )
                db.add(rule)

        new_persons.append(person)

    await db.commit()

    # Return full coverage structure
    return await _build_coverage(db, contract_id)


@router.get("/{contract_id}/coverage", response_model=ContractCoverageRead)
async def get_contract_coverage(
    contract_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Returns per-person, per-tariff coverage with benefit rules and usage."""
    contract = await db.get(InsuranceContract, contract_id)
    _assert_owned(contract, current_user.id)
    return await _build_coverage(db, contract_id)


@router.get("/{contract_id}/benefits", response_model=list[BenefitRuleWithRemaining])
async def get_benefit_quotas(
    contract_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Returns each benefit rule with the amount used and remaining quota."""
    contract = await db.get(InsuranceContract, contract_id)
    _assert_owned(contract, current_user.id)

    result = await db.execute(
        select(BenefitRule).where(BenefitRule.contract_id == contract_id)
    )
    rules = result.scalars().all()

    enriched = []
    for rule in rules:
        used_result = await db.execute(
            select(func.coalesce(func.sum(BenefitUsage.amount_used), 0.0))
            .where(BenefitUsage.benefit_rule_id == rule.id)
        )
        amount_used = used_result.scalar()
        amount_remaining = (
            max(0.0, rule.limit_amount - amount_used)
            if rule.limit_amount is not None
            else None
        )
        enriched.append(
            BenefitRuleWithRemaining(
                **BenefitRuleRead.model_validate(rule).model_dump(),
                amount_used=amount_used,
                amount_remaining=amount_remaining,
            )
        )
    return enriched


@router.post("/{contract_id}/benefits", response_model=BenefitRuleRead, status_code=status.HTTP_201_CREATED)
async def create_benefit_rule(
    contract_id: UUID,
    payload: BenefitRuleCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    contract = await db.get(InsuranceContract, contract_id)
    _assert_owned(contract, current_user.id)
    rule = BenefitRule(contract_id=contract_id, **payload.model_dump())
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    return rule


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _assert_owned(obj, user_id: UUID) -> None:
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    if obj.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")


_HONORIFICS = {"mag", "dr", "prof", "ing", "dipl", "msc", "mba", "bsc", "phd", "ddr", "ao", "univ"}


def _match_family_member(full_name: str, family_members) -> UUID | None:
    """
    Case-insensitive first-name match against FamilyMember.name.
    Skips Austrian academic titles/honorifics (MSc, Dipl.Ing., Dr., etc.)
    so that 'MSc Jennifer Ladenhauf' matches the member named 'Jennifer'.
    """
    if not full_name:
        return None
    first_name = None
    for token in full_name.split():
        # Skip tokens that are honorifics: end with '.' or are known abbreviations
        normalised = token.lower().rstrip(".")
        if token.endswith(".") or normalised in _HONORIFICS:
            continue
        first_name = token.lower()
        break
    if not first_name:
        return None
    for member in family_members:
        member_first = member.name.split()[0].lower() if member.name.split() else ""
        if member_first and first_name == member_first:
            return member.id
    return None


def _parse_date(date_str: str | None):
    if not date_str:
        return None
    from datetime import datetime, timezone
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d.%m.%y"):
        try:
            return datetime.strptime(date_str, fmt).replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            continue
    return None


def _coerce_float(val) -> float | None:
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _coerce_enum(enum_cls, val):
    if val is None:
        return None
    try:
        return enum_cls(val)
    except ValueError:
        return None


async def _build_coverage(db: AsyncSession, contract_id: UUID) -> ContractCoverageRead:
    """Load persons → tariffs → benefits with usage, return ContractCoverageRead."""
    persons_result = await db.execute(
        select(InsuredPerson)
        .where(InsuredPerson.contract_id == contract_id)
        .options(selectinload(InsuredPerson.tariffs).selectinload(Tariff.benefit_rules))
    )
    persons = persons_result.scalars().all()

    # Collect all benefit_rule ids to batch-fetch usages
    all_rule_ids = [
        rule.id
        for person in persons
        for tariff in person.tariffs
        for rule in tariff.benefit_rules
    ]

    usage_map: dict[UUID, float] = {}
    if all_rule_ids:
        usage_result = await db.execute(
            select(BenefitUsage.benefit_rule_id, func.sum(BenefitUsage.amount_used))
            .where(BenefitUsage.benefit_rule_id.in_(all_rule_ids))
            .group_by(BenefitUsage.benefit_rule_id)
        )
        usage_map = {row[0]: row[1] for row in usage_result}

    person_reads = []
    for person in persons:
        tariff_reads = []
        for tariff in person.tariffs:
            benefit_reads = []
            for rule in tariff.benefit_rules:
                used = usage_map.get(rule.id, 0.0)
                remaining = (
                    max(0.0, rule.limit_amount - used)
                    if rule.limit_amount is not None
                    else None
                )
                benefit_reads.append(
                    BenefitRuleDetailRead(
                        id=rule.id,
                        contract_id=rule.contract_id,
                        tariff_id=rule.tariff_id,
                        benefit_name=rule.benefit_name,
                        benefit_kind=rule.benefit_kind,
                        limit_amount=rule.limit_amount,
                        reimbursement_pct=rule.reimbursement_pct,
                        reset_period=rule.reset_period,
                        category=rule.category,
                        notes=rule.notes,
                        amount_used=used,
                        amount_remaining=remaining,
                    )
                )
            tariff_reads.append(
                TariffRead(
                    id=tariff.id,
                    insured_person_id=tariff.insured_person_id,
                    code=tariff.code,
                    name=tariff.name,
                    description_raw=tariff.description_raw,
                    program_info=tariff.program_info,
                    benefits=benefit_reads,
                )
            )
        person_reads.append(
            InsuredPersonRead(
                id=person.id,
                contract_id=person.contract_id,
                family_member_id=person.family_member_id,
                full_name=person.full_name,
                kd_nr=person.kd_nr,
                birth_date=person.birth_date,
                tariffs=tariff_reads,
            )
        )

    return ContractCoverageRead(contract_id=contract_id, insured_persons=person_reads)
