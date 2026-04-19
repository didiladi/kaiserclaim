from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_current_user
from core.config import get_settings
from core.database import get_db
from models.domain import BenefitRule, InsuranceContract, User
from schemas.payload import (
    BenefitRuleRead,
    BenefitRuleWithRemaining,
    ContractCreate,
    ContractRead,
)
from services.llm_auditor import parse_contract
from services.ocr_engine import pdf_to_text

settings = get_settings()
router = APIRouter(prefix="/contracts", tags=["contracts"])


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


@router.post("/{contract_id}/parse-pdf", response_model=list[BenefitRuleRead])
async def parse_contract_pdf(
    contract_id: UUID,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Upload the insurance contract PDF. Runs OCR then sends text to Gemini
    to extract BenefitRules. Existing rules for this contract are replaced.
    """
    contract = await db.get(InsuranceContract, contract_id)
    _assert_owned(contract, current_user.id)

    import tempfile, shutil
    from pathlib import Path

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name

    text = await pdf_to_text(tmp_path)
    Path(tmp_path).unlink(missing_ok=True)

    parsed_rules = await parse_contract(text)

    # Replace existing rules
    existing = await db.execute(select(BenefitRule).where(BenefitRule.contract_id == contract_id))
    for rule in existing.scalars().all():
        await db.delete(rule)

    new_rules = [
        BenefitRule(contract_id=contract_id, **rule.model_dump())
        for rule in parsed_rules
    ]
    db.add_all(new_rules)
    await db.commit()
    for rule in new_rules:
        await db.refresh(rule)
    return new_rules


@router.get("/{contract_id}/benefits", response_model=list[BenefitRuleWithRemaining])
async def get_benefit_quotas(
    contract_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Returns each benefit rule with the amount used and remaining quota."""
    from sqlalchemy import func
    from models.domain import BenefitUsage

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
        enriched.append(
            BenefitRuleWithRemaining(
                **BenefitRuleRead.model_validate(rule).model_dump(),
                amount_used=amount_used,
                amount_remaining=max(0.0, rule.limit_amount - amount_used),
            )
        )
    return enriched


def _assert_owned(obj, user_id: UUID) -> None:
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    if obj.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
