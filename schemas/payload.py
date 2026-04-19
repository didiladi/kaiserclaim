from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, ConfigDict

from models.domain import InvoiceStatus, LimitType


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
    limit_amount: float
    limit_type: LimitType
    reset_date: Optional[datetime] = None


class BenefitRuleRead(_Base):
    id: uuid.UUID
    contract_id: uuid.UUID
    benefit_name: str
    limit_amount: float
    limit_type: LimitType
    reset_date: Optional[datetime]


class BenefitRuleWithRemaining(BenefitRuleRead):
    """Augmented view used by the Auditor dashboard — remaining quota is computed at query time."""
    amount_used: float
    amount_remaining: float


# ---------------------------------------------------------------------------
# Invoice
# ---------------------------------------------------------------------------

class InvoiceCreate(BaseModel):
    file_path: str
    provider_name: Optional[str] = None
    patient_name: Optional[str] = None
    amount: Optional[float] = None
    date: Optional[datetime] = None


class InvoiceStatusUpdate(BaseModel):
    status: InvoiceStatus


class InvoiceRead(_Base):
    id: uuid.UUID
    user_id: uuid.UUID
    file_path: str
    provider_name: Optional[str]
    patient_name: Optional[str]
    amount: Optional[float]
    date: Optional[datetime]
    status: InvoiceStatus
    created_at: datetime
    updated_at: datetime


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
