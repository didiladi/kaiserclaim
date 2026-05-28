"""Add per-person coverage: InsuredPerson, Tariff, enrich BenefitRule.

Revision ID: 0006
Revises: 0005
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- New enums ---
    resetperiod = sa.Enum(
        "CALENDAR_YEAR", "INSURANCE_YEAR", "PER_EVENT", "ONCE_PER_YEAR",
        name="resetperiod",
    )
    benefitkind = sa.Enum("BUDGET", "PROGRAM", "DEDUCTIBLE", name="benefitkind")
    resetperiod.create(op.get_bind())
    benefitkind.create(op.get_bind())

    # --- insured_persons ---
    op.create_table(
        "insured_persons",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("contract_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("family_member_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("full_name", sa.String(), nullable=False),
        sa.Column("kd_nr", sa.String(), nullable=True),
        sa.Column("birth_date", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["contract_id"], ["insurance_contracts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["family_member_id"], ["family_members.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_insured_persons_contract_id", "insured_persons", ["contract_id"])

    # --- tariffs ---
    op.create_table(
        "tariffs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("insured_person_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("description_raw", sa.Text(), nullable=True),
        sa.Column("program_info", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["insured_person_id"], ["insured_persons.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tariffs_insured_person_id", "tariffs", ["insured_person_id"])

    # --- benefit_rules: new columns ---
    op.add_column("benefit_rules", sa.Column("tariff_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_benefit_rules_tariff_id",
        "benefit_rules", "tariffs",
        ["tariff_id"], ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_benefit_rules_tariff_id", "benefit_rules", ["tariff_id"])

    op.add_column("benefit_rules", sa.Column("benefit_kind", sa.Enum("BUDGET", "PROGRAM", "DEDUCTIBLE", name="benefitkind", create_type=False), nullable=True))
    op.add_column("benefit_rules", sa.Column("reset_period", sa.Enum("CALENDAR_YEAR", "INSURANCE_YEAR", "PER_EVENT", "ONCE_PER_YEAR", name="resetperiod", create_type=False), nullable=True))
    op.add_column("benefit_rules", sa.Column("reimbursement_pct", sa.Float(), nullable=True))
    op.add_column("benefit_rules", sa.Column("category", sa.String(), nullable=True))
    op.add_column("benefit_rules", sa.Column("notes", sa.Text(), nullable=True))

    # Make limit_amount and limit_type nullable (PROGRAM benefits have no euro cap)
    op.alter_column("benefit_rules", "limit_amount", nullable=True)
    op.alter_column("benefit_rules", "limit_type", nullable=True)


def downgrade() -> None:
    op.alter_column("benefit_rules", "limit_type", nullable=False)
    op.alter_column("benefit_rules", "limit_amount", nullable=False)

    op.drop_column("benefit_rules", "notes")
    op.drop_column("benefit_rules", "category")
    op.drop_column("benefit_rules", "reimbursement_pct")
    op.drop_column("benefit_rules", "reset_period")
    op.drop_column("benefit_rules", "benefit_kind")

    op.drop_constraint("fk_benefit_rules_tariff_id", "benefit_rules", type_="foreignkey")
    op.drop_index("ix_benefit_rules_tariff_id", "benefit_rules")
    op.drop_column("benefit_rules", "tariff_id")

    op.drop_index("ix_tariffs_insured_person_id", "tariffs")
    op.drop_table("tariffs")

    op.drop_index("ix_insured_persons_contract_id", "insured_persons")
    op.drop_table("insured_persons")

    sa.Enum(name="benefitkind").drop(op.get_bind())
    sa.Enum(name="resetperiod").drop(op.get_bind())
