"""add invoice.benefit_rule_id

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-17

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "invoices",
        sa.Column(
            "benefit_rule_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("benefit_rules.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_invoices_benefit_rule_id", "invoices", ["benefit_rule_id"])


def downgrade() -> None:
    op.drop_index("ix_invoices_benefit_rule_id", table_name="invoices")
    op.drop_column("invoices", "benefit_rule_id")
