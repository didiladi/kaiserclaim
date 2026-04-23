"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-04-22

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create enum types explicitly so they exist before the tables reference them.
    op.execute("CREATE TYPE limittype AS ENUM ('YEARLY', 'BIANNUAL')")
    op.execute(
        "CREATE TYPE invoicestatus AS ENUM ("
        "'RECEIVED', 'OCR_PROCESSING', 'READY_FOR_OEGK', 'OEGK_SUBMITTED',"
        "'OEGK_REFUNDED', 'READY_FOR_MERKUR', 'MERKUR_SUBMITTED', 'COMPLETED')"
    )

    # --- users ---
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # --- insurance_contracts ---
    op.create_table(
        "insurance_contracts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider_name", sa.String(), nullable=False),
        sa.Column("policy_number", sa.String(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_insurance_contracts_user_id", "insurance_contracts", ["user_id"])

    # --- benefit_rules ---
    op.create_table(
        "benefit_rules",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("contract_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("benefit_name", sa.String(), nullable=False),
        sa.Column("limit_amount", sa.Float(), nullable=False),
        sa.Column(
            "limit_type",
            postgresql.ENUM("YEARLY", "BIANNUAL", name="limittype", create_type=False),
            nullable=False,
        ),
        sa.Column("reset_date", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["contract_id"], ["insurance_contracts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_benefit_rules_contract_id", "benefit_rules", ["contract_id"])

    # --- invoices ---
    op.create_table(
        "invoices",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("file_path", sa.String(), nullable=False),
        sa.Column("provider_name", sa.String(), nullable=True),
        sa.Column("patient_name", sa.String(), nullable=True),
        sa.Column("amount", sa.Float(), nullable=True),
        sa.Column("date", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM(
                "RECEIVED",
                "OCR_PROCESSING",
                "READY_FOR_OEGK",
                "OEGK_SUBMITTED",
                "OEGK_REFUNDED",
                "READY_FOR_MERKUR",
                "MERKUR_SUBMITTED",
                "COMPLETED",
                name="invoicestatus",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_invoices_user_id", "invoices", ["user_id"])

    # --- benefit_usages ---
    op.create_table(
        "benefit_usages",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("invoice_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("benefit_rule_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("amount_used", sa.Float(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["benefit_rule_id"], ["benefit_rules.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["invoice_id"], ["invoices.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_benefit_usages_invoice_id", "benefit_usages", ["invoice_id"])
    op.create_index("ix_benefit_usages_benefit_rule_id", "benefit_usages", ["benefit_rule_id"])


def downgrade() -> None:
    op.drop_table("benefit_usages")
    op.drop_table("invoices")
    op.drop_table("benefit_rules")
    op.drop_table("insurance_contracts")
    op.drop_table("users")

    op.execute("DROP TYPE IF EXISTS invoicestatus")
    op.execute("DROP TYPE IF EXISTS limittype")
