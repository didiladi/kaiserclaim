"""add merkur documents and outcome statuses

Revision ID: 0004
Revises: 0003
Create Date: 2026-05-22

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ALTER TYPE … ADD VALUE must run outside a transaction in Postgres.
    # Alembic's default transaction wrapping is off for this migration.
    op.execute("ALTER TYPE invoicestatus ADD VALUE IF NOT EXISTS 'MERKUR_REIMBURSED'")
    op.execute("ALTER TYPE invoicestatus ADD VALUE IF NOT EXISTS 'MERKUR_REJECTED'")

    op.execute(
        "CREATE TYPE merkurresultstate AS ENUM ('REIMBURSED', 'REJECTED', 'UNKNOWN')"
    )

    op.create_table(
        "merkur_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("geschaeftsfall_nr", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("document_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("file_path", sa.String(), nullable=False),
        sa.Column("patient_name", sa.String(), nullable=True),
        sa.Column("invoice_amount", sa.Float(), nullable=True),
        sa.Column("reimbursed_amount", sa.Float(), nullable=True),
        sa.Column(
            "result_state",
            postgresql.ENUM("REIMBURSED", "REJECTED", "UNKNOWN", name="merkurresultstate", create_type=False),
            nullable=False,
        ),
        sa.Column("raw_text", sa.Text(), nullable=True),
        sa.Column("invoice_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["invoice_id"], ["invoices.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("geschaeftsfall_nr"),
    )
    op.create_index("ix_merkur_documents_user_id", "merkur_documents", ["user_id"])
    op.create_index("ix_merkur_documents_geschaeftsfall_nr", "merkur_documents", ["geschaeftsfall_nr"])
    op.create_index("ix_merkur_documents_invoice_id", "merkur_documents", ["invoice_id"])


def downgrade() -> None:
    op.drop_index("ix_merkur_documents_invoice_id", table_name="merkur_documents")
    op.drop_index("ix_merkur_documents_geschaeftsfall_nr", table_name="merkur_documents")
    op.drop_index("ix_merkur_documents_user_id", table_name="merkur_documents")
    op.drop_table("merkur_documents")
    op.execute("DROP TYPE IF EXISTS merkurresultstate")
    # Note: Postgres does not support DROP VALUE on enums — MERKUR_REIMBURSED/REJECTED
    # remain in the invoicestatus enum after downgrade, which is harmless.
