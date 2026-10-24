"""add oegk_documents and family_members.svnr

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-24

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("family_members", sa.Column("svnr", sa.String(), nullable=True))
    op.create_table(
        "oegk_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("dedupe_key", sa.String(), nullable=False),
        sa.Column("file_path", sa.String(), nullable=True),
        sa.Column("patient_name", sa.String(), nullable=True),
        sa.Column("doctor_name", sa.String(), nullable=True),
        sa.Column("service_date", sa.Date(), nullable=True),
        sa.Column("payout_date", sa.Date(), nullable=True),
        sa.Column("invoice_amount", sa.Float(), nullable=True),
        sa.Column("reimbursed_amount", sa.Float(), nullable=True),
        sa.Column("family_member_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("family_members.id", ondelete="SET NULL"), nullable=True),
        sa.Column("invoice_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("invoices.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_oegk_documents_user_id", "oegk_documents", ["user_id"])
    op.create_index("ix_oegk_documents_dedupe_key", "oegk_documents", ["dedupe_key"], unique=True)
    op.create_index("ix_oegk_documents_invoice_id", "oegk_documents", ["invoice_id"])


def downgrade() -> None:
    op.drop_table("oegk_documents")
    op.drop_column("family_members", "svnr")
