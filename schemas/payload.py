from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional, Literal, List

from pydantic import BaseModel, EmailStr, ConfigDict, Field

from models.domain import InvoiceStatus, LimitType, MerkurResultState, BenefitKind, ResetPeriod


# ---------------------------------------------------------------------------
# Shared config
# ---------------------------------------------------------------------------

class _Base(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# User
# ---------------------------------------------------------------------------

class UserCreate(BaseModel):
    email: EmailStr


class UserRead(_Base):
    id: uuid.UUID
    email: str
    created_at: datetime


# ---------------------------------------------------------------------------
# FamilyMember
# ---------------------------------------------------------------------------

_SVNR = r"^\d{10}$"


class FamilyMemberCreate(BaseModel):
    member_key: str
    name: str
    color: str
    initials: str
    svnr: Optional[str] = Field(default=None, pattern=_SVNR)


class FamilyMemberUpdate(BaseModel):
    """svnr is write-only PII: Read only reports whether one is stored."""
    svnr: Optional[str] = Field(default=None, pattern=_SVNR)


class FamilyMemberRead(_Base):
    id: uuid.UUID
    user_id: uuid.UUID
    member_key: str
    name: str
    color: str
    initials: str
    has_svnr: bool = False
    created_at: datetime


# ---------------------------------------------------------------------------
# ÖGK refund PDFs
# ---------------------------------------------------------------------------

class OegkIngestRead(BaseModel):
    outcome: Literal["not_a_refund", "duplicate", "linked", "unmatched", "ambiguous"]
    document_id: Optional[uuid.UUID] = None
    invoice_id: Optional[uuid.UUID] = None
    is_new: bool = False


# ---------------------------------------------------------------------------
# InsuranceContract
# ---------------------------------------------------------------------------

class ContractCreate(BaseModel):
    provider_name: str
    policy_number: Optional[str] = None


class ContractRead(_Base):
    id: uuid.UUID
    user_id: uuid.UUID
    provider_name: str
    policy_number: Optional[str]
    created_at: datetime


# ---------------------------------------------------------------------------
# BenefitRule
# ---------------------------------------------------------------------------

class BenefitRuleCreate(BaseModel):
    benefit_name: str
    limit_amount: Optional[float] = None
    limit_type: Optional[LimitType] = None
    reset_date: Optional[datetime] = None


class BenefitRuleRead(_Base):
    id: uuid.UUID
    contract_id: uuid.UUID
    benefit_name: str
    limit_amount: Optional[float]
    limit_type: Optional[LimitType]
    reset_date: Optional[datetime]


class BenefitRuleWithRemaining(BenefitRuleRead):
    """Augmented view used by the Auditor dashboard — remaining quota is computed at query time."""
    amount_used: float
    amount_remaining: Optional[float]  # null for PROGRAM benefits with no euro cap


# ---------------------------------------------------------------------------
# Per-person coverage (new)
# ---------------------------------------------------------------------------

class BenefitRuleDetailRead(_Base):
    id: uuid.UUID
    contract_id: uuid.UUID
    tariff_id: Optional[uuid.UUID]
    benefit_name: str
    benefit_kind: Optional[BenefitKind]
    limit_amount: Optional[float]
    reimbursement_pct: Optional[float]
    reset_period: Optional[ResetPeriod]
    category: Optional[str]
    notes: Optional[str]
    amount_used: float = 0.0
    amount_remaining: Optional[float] = None


class TariffRead(_Base):
    id: uuid.UUID
    insured_person_id: uuid.UUID
    code: str
    name: Optional[str]
    description_raw: Optional[str]
    program_info: Optional[str]
    benefits: List[BenefitRuleDetailRead] = []


class InsuredPersonRead(_Base):
    id: uuid.UUID
    contract_id: uuid.UUID
    family_member_id: Optional[uuid.UUID]
    full_name: str
    kd_nr: Optional[str]
    birth_date: Optional[datetime]
    tariffs: List[TariffRead] = []


class ContractCoverageRead(BaseModel):
    contract_id: uuid.UUID
    insured_persons: List[InsuredPersonRead] = []


# ---------------------------------------------------------------------------
# Invoice
# ---------------------------------------------------------------------------

class InvoiceStatusUpdate(BaseModel):
    status: InvoiceStatus


class InvoiceCorrection(BaseModel):
    """Manual fix-up of fields OCR could not extract (NEEDS_REVIEW recovery)."""
    amount: Optional[float] = Field(default=None, gt=0)
    date: Optional[datetime] = None
    provider_name: Optional[str] = None
    patient_name: Optional[str] = None


# Pipeline variant: pharmacy skips ÖGK; standard goes through all 8 steps.
_PHARMACY_CATEGORIES = {"medikamente", "apotheke", "pharmaz"}

def _derive_pipeline(category: Optional[str]) -> Literal["standard", "pharmacy"]:
    if category and any(k in category.lower() for k in _PHARMACY_CATEGORIES):
        return "pharmacy"
    return "standard"

def first_submission_status(category: Optional[str]) -> InvoiceStatus:
    """Where a fully-parsed invoice goes next.

    Only invoices with an explicitly chosen non-pharmacy category take the ÖGK
    route. An unset category keeps the original behaviour (straight to Merkur),
    so uploads that never picked a category are not silently rerouted.
    """
    if category and _derive_pipeline(category) == "standard":
        return InvoiceStatus.READY_FOR_OEGK
    return InvoiceStatus.READY_FOR_MERKUR


# Ordered list of statuses — index = current_step
_STATUS_ORDER = [
    InvoiceStatus.RECEIVED,
    InvoiceStatus.OCR_PROCESSING,
    InvoiceStatus.READY_FOR_OEGK,
    InvoiceStatus.OEGK_SUBMITTING,
    InvoiceStatus.OEGK_SUBMITTED,
    InvoiceStatus.OEGK_REFUNDED,
    InvoiceStatus.READY_FOR_MERKUR,
    InvoiceStatus.MERKUR_SUBMITTING,
    InvoiceStatus.MERKUR_SUBMITTED,
    InvoiceStatus.MERKUR_REIMBURSED,
    InvoiceStatus.MERKUR_REJECTED,
    InvoiceStatus.COMPLETED,
]

def _current_step(status: InvoiceStatus) -> int:
    try:
        return _STATUS_ORDER.index(status)
    except ValueError:
        return 0


class InvoiceRead(_Base):
    id: uuid.UUID
    user_id: uuid.UUID
    file_path: str
    provider_name: Optional[str]
    patient_name: Optional[str]
    amount: Optional[float]
    date: Optional[datetime]
    benefit_rule_id: Optional[uuid.UUID]
    category: Optional[str]
    family_member_id: Optional[uuid.UUID]
    status: InvoiceStatus
    created_at: datetime
    updated_at: datetime
    pipeline: Literal["standard", "pharmacy"] = "standard"
    current_step: int = 0
    reimbursed_amount: Optional[float] = None
    result_state: Optional[str] = None

    @classmethod
    def model_validate(cls, obj, **kwargs):
        instance = super().model_validate(obj, **kwargs)
        instance.pipeline = _derive_pipeline(instance.category)
        instance.current_step = _current_step(instance.status)
        # Populate reimbursement info from the linked MerkurDocument (if eagerly loaded)
        try:
            doc = getattr(obj, "merkur_document", None)
            if doc is not None:
                instance.reimbursed_amount = doc.reimbursed_amount
                instance.result_state = doc.result_state.value if doc.result_state else None
        except Exception:
            pass
        return instance


# ---------------------------------------------------------------------------
# BenefitUsage
# ---------------------------------------------------------------------------

class BenefitUsageCreate(BaseModel):
    benefit_rule_id: uuid.UUID
    amount_used: float


class BenefitUsageRead(_Base):
    id: uuid.UUID
    invoice_id: uuid.UUID
    benefit_rule_id: uuid.UUID
    amount_used: float
    created_at: datetime


# ---------------------------------------------------------------------------
# MerkurDocument
# ---------------------------------------------------------------------------

class MerkurDocumentRead(_Base):
    id: uuid.UUID
    user_id: uuid.UUID
    geschaeftsfall_nr: str
    title: str
    document_date: Optional[datetime]
    file_path: Optional[str]
    patient_name: Optional[str]
    invoice_amount: Optional[float]
    reimbursed_amount: Optional[float]
    result_state: MerkurResultState
    invoice_id: Optional[uuid.UUID]
    created_at: datetime
