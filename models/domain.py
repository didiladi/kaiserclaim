import uuid
import enum
from datetime import datetime

from sqlalchemy import (
    Column, String, Float, DateTime, ForeignKey, Enum as SAEnum, Text, func
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


class ResetPeriod(str, enum.Enum):
    CALENDAR_YEAR = "CALENDAR_YEAR"
    INSURANCE_YEAR = "INSURANCE_YEAR"
    PER_EVENT = "PER_EVENT"
    ONCE_PER_YEAR = "ONCE_PER_YEAR"


class BenefitKind(str, enum.Enum):
    BUDGET = "BUDGET"
    PROGRAM = "PROGRAM"
    DEDUCTIBLE = "DEDUCTIBLE"


class InvoiceStatus(str, enum.Enum):
    RECEIVED = "RECEIVED"
    OCR_PROCESSING = "OCR_PROCESSING"
    READY_FOR_OEGK = "READY_FOR_OEGK"
    OEGK_SUBMITTED = "OEGK_SUBMITTED"
    OEGK_REFUNDED = "OEGK_REFUNDED"
    READY_FOR_MERKUR = "READY_FOR_MERKUR"
    MERKUR_SUBMITTED = "MERKUR_SUBMITTED"
    MERKUR_REIMBURSED = "MERKUR_REIMBURSED"
    MERKUR_REJECTED = "MERKUR_REJECTED"
    COMPLETED = "COMPLETED"


class MerkurResultState(str, enum.Enum):
    REIMBURSED = "REIMBURSED"
    REJECTED = "REJECTED"
    UNKNOWN = "UNKNOWN"


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
    family_members = relationship("FamilyMember", back_populates="user", cascade="all, delete-orphan")
    merkur_documents = relationship("MerkurDocument", back_populates="user", cascade="all, delete-orphan")


class FamilyMember(Base):
    __tablename__ = "family_members"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    member_key = Column(String, nullable=False)   # stable slug: 'maria', 'thomas', etc. — used as FK by FE
    name = Column(String, nullable=False)
    color = Column(String, nullable=False)        # hex color, e.g. '#E84393'
    initials = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user = relationship("User", back_populates="family_members")
    invoices = relationship("Invoice", back_populates="family_member")


class InsuranceContract(Base):
    __tablename__ = "insurance_contracts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    provider_name = Column(String, nullable=False)       # e.g. "Merkur"
    policy_number = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user = relationship("User", back_populates="contracts")
    benefit_rules = relationship("BenefitRule", back_populates="contract", cascade="all, delete-orphan")
    insured_persons = relationship("InsuredPerson", back_populates="contract", cascade="all, delete-orphan")



class InsuredPerson(Base):
    __tablename__ = "insured_persons"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    contract_id = Column(UUID(as_uuid=True), ForeignKey("insurance_contracts.id", ondelete="CASCADE"), nullable=False, index=True)
    family_member_id = Column(UUID(as_uuid=True), ForeignKey("family_members.id", ondelete="SET NULL"), nullable=True)
    full_name = Column(String, nullable=False)
    kd_nr = Column(String, nullable=True)
    birth_date = Column(DateTime(timezone=True), nullable=True)

    contract = relationship("InsuranceContract", back_populates="insured_persons")
    family_member = relationship("FamilyMember")
    tariffs = relationship("Tariff", back_populates="insured_person", cascade="all, delete-orphan")


class Tariff(Base):
    __tablename__ = "tariffs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    insured_person_id = Column(UUID(as_uuid=True), ForeignKey("insured_persons.id", ondelete="CASCADE"), nullable=False, index=True)
    code = Column(String, nullable=False)            # e.g. "MHNG1E25S1"
    name = Column(String, nullable=True)             # e.g. "NOVUM SMART"
    description_raw = Column(Text, nullable=True)
    program_info = Column(Text, nullable=True)        # web-enriched (Phase 1.5)

    insured_person = relationship("InsuredPerson", back_populates="tariffs")
    benefit_rules = relationship("BenefitRule", back_populates="tariff", cascade="all, delete-orphan")


class BenefitRule(Base):
    __tablename__ = "benefit_rules"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    contract_id = Column(UUID(as_uuid=True), ForeignKey("insurance_contracts.id", ondelete="CASCADE"), nullable=False, index=True)
    # Per-person linkage (null for legacy contract-level benefits)
    tariff_id = Column(UUID(as_uuid=True), ForeignKey("tariffs.id", ondelete="CASCADE"), nullable=True, index=True)
    benefit_name = Column(String, nullable=False)            # e.g. "Zahnreinigung"
    benefit_kind = Column(SAEnum(BenefitKind, name="benefitkind", create_type=False), nullable=True)
    limit_amount = Column(Float, nullable=True)              # null for PROGRAM benefits
    limit_type = Column(SAEnum(LimitType), nullable=True)    # legacy field; use reset_period for new records
    reset_period = Column(SAEnum(ResetPeriod, name="resetperiod", create_type=False), nullable=True)
    reset_date = Column(DateTime(timezone=True), nullable=True)  # next quota reset
    reimbursement_pct = Column(Float, nullable=True)         # e.g. 80.0 (percent)
    category = Column(String, nullable=True)                 # maps to BENEFIT_CATEGORIES token keys
    notes = Column(Text, nullable=True)

    contract = relationship("InsuranceContract", back_populates="benefit_rules")
    tariff = relationship("Tariff", back_populates="benefit_rules")
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

    benefit_rule_id = Column(UUID(as_uuid=True), ForeignKey("benefit_rules.id", ondelete="SET NULL"), nullable=True, index=True)
    # Denormalized benefit/category label for display when benefit_rule_id is not set
    category = Column(String, nullable=True)
    # FK to the family member this invoice belongs to
    family_member_id = Column(UUID(as_uuid=True), ForeignKey("family_members.id", ondelete="SET NULL"), nullable=True, index=True)

    user = relationship("User", back_populates="invoices")
    family_member = relationship("FamilyMember", back_populates="invoices")
    benefit_usages = relationship("BenefitUsage", back_populates="invoice", cascade="all, delete-orphan")
    merkur_document = relationship("MerkurDocument", back_populates="invoice", uselist=False)


class BenefitUsage(Base):
    __tablename__ = "benefit_usages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    invoice_id = Column(UUID(as_uuid=True), ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False, index=True)
    benefit_rule_id = Column(UUID(as_uuid=True), ForeignKey("benefit_rules.id", ondelete="CASCADE"), nullable=False, index=True)
    amount_used = Column(Float, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    invoice = relationship("Invoice", back_populates="benefit_usages")
    benefit_rule = relationship("BenefitRule", back_populates="usages")


class MerkurDocument(Base):
    __tablename__ = "merkur_documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    geschaeftsfall_nr = Column(String, unique=True, nullable=False, index=True)
    title = Column(String, nullable=False)
    document_date = Column(DateTime(timezone=True), nullable=True)
    file_path = Column(String, nullable=True)
    patient_name = Column(String, nullable=True)
    invoice_amount = Column(Float, nullable=True)
    reimbursed_amount = Column(Float, nullable=True)
    result_state = Column(SAEnum(MerkurResultState, name="merkurresultstate", create_type=False), nullable=False)
    raw_text = Column(Text, nullable=True)
    invoice_id = Column(UUID(as_uuid=True), ForeignKey("invoices.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user = relationship("User", back_populates="merkur_documents")
    invoice = relationship("Invoice", back_populates="merkur_document")
