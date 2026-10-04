"""add OEGK_SUBMITTING invoice status

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-04

"""
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE invoicestatus ADD VALUE IF NOT EXISTS 'OEGK_SUBMITTING'")


def downgrade() -> None:
    # Postgres cannot drop enum values; OEGK_SUBMITTING stays, harmlessly.
    pass
