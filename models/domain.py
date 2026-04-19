import uuid
import enum
from datetime import datetime

from sqlalchemy import (
    Column, String, Float, DateTime, ForeignKey, Enum as SAEnum, func
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class LimitType(str, enum.Enum):
    YEARLY = "YEARLY"
    BIANNUAL = "BIANNUAL"


class InvoiceStatus(str, enum.Enum):
    RECEIVED = "RECEIVED"
    OCR_PROCESSING = "OCR_PROCESSING"
    READY_FOR_OEGK = "READY_FOR_OEGK"
    OEGK_SUBMITTED = "OEGK_SUBMITTED"
    OEGK_REFUNDED = "OEGK_REFUNDED"
    READY_FOR_MERKUR = "READY_FOR_MERKUR"
    MERKUR_SUBMITTED = "MERKUR_SUBMITTED"
    COMPLETED = "COMPLETED"


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    contracts = relationship("InsuranceContract", back_populates="user", cascade="all, delete-orphan")
    invoices = relationship("Invoice", back_populates="user", cascade="all, delete-orphan")


class InsuranceContract(Base):
    __tablename__ = "insurance_contracts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    provider_name = Column(String, nullable=False)       # e.g. "Merkur"
    policy_number = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user = relationship("User", back_populates="contracts")
    benefit_rules = relationship("BenefitRule", back_populates="contract", cascade="all, delete-orphan")


class BenefitRule(Base):
    __tablename__ = "benefit_rules"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    contract_id = Column(UUID(as_uuid=True), ForeignKey("insurance_contracts.id", ondelete="CASCADE"), nullable=False, index=True)
    benefit_name = Column(String, nullable=False)        # e.g. "Zahnreinigung"
    limit_amount = Column(Float, nullable=False)         # e.g. 150.0
    limit_type = Column(SAEnum(LimitType), nullable=False)
    reset_date = Column(DateTime(timezone=True), nullable=True)  # next quota reset

    contract = relationship("InsuranceContract", back_populates="benefit_rules")
    usages = relationship("BenefitUsage", back_populates="benefit_rule", cascade="all, delete-orphan")


class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    file_path = Column(String, nullable=False)
    provider_name = Column(String, nullable=True)        # e.g. "Apotheke Zur Gesundheit"
    patient_name = Column(String, nullable=True)
    amount = Column(Float, nullable=True)
    date = Column(DateTime(timezone=True), nullable=True)
    status = Column(SAEnum(InvoiceStatus), nullable=False, default=InvoiceStatus.RECEIVED)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    user = relationship("User", back_populates="invoices")
    benefit_usages = relationship("BenefitUsage", back_populates="invoice", cascade="all, delete-orphan")


class BenefitUsage(Base):
    __tablename__ = "benefit_usages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    invoice_id = Column(UUID(as_uuid=True), ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False, index=True)
    benefit_rule_id = Column(UUID(as_uuid=True), ForeignKey("benefit_rules.id", ondelete="CASCADE"), nullable=False, index=True)
    amount_used = Column(Float, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    invoice = relationship("Invoice", back_populates="benefit_usages")
    benefit_rule = relationship("BenefitRule", back_populates="usages")
