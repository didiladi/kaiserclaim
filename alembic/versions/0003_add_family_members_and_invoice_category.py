"""add family_members table, invoice.category, invoice.family_member_id

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-21

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "family_members",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("member_key", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("color", sa.String(), nullable=False),
        sa.Column("initials", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_family_members_user_id", "family_members", ["user_id"])

    op.add_column("invoices", sa.Column("category", sa.String(), nullable=True))
    op.add_column(
        "invoices",
        sa.Column(
            "family_member_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("family_members.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_invoices_family_member_id", "invoices", ["family_member_id"])


def downgrade() -> None:
    op.drop_index("ix_invoices_family_member_id", table_name="invoices")
    op.drop_column("invoices", "family_member_id")
    op.drop_column("invoices", "category")
    op.drop_index("ix_family_members_user_id", table_name="family_members")
    op.drop_table("family_members")
