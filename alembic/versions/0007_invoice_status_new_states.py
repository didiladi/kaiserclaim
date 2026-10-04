"""add MERKUR_SUBMITTING, NEEDS_REVIEW, FAILED invoice statuses

Revision ID: 0007
Revises: 0006
Create Date: 2026-08-03

"""
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ALTER TYPE … ADD VALUE must run outside a transaction in Postgres.
    # Alembic's default transaction wrapping is off for this migration.
    op.execute("ALTER TYPE invoicestatus ADD VALUE IF NOT EXISTS 'MERKUR_SUBMITTING'")
    op.execute("ALTER TYPE invoicestatus ADD VALUE IF NOT EXISTS 'NEEDS_REVIEW'")
    op.execute("ALTER TYPE invoicestatus ADD VALUE IF NOT EXISTS 'FAILED'")


def downgrade() -> None:
    # Note: Postgres does not support DROP VALUE on enums — MERKUR_SUBMITTING,
    # NEEDS_REVIEW, FAILED remain in the invoicestatus enum after downgrade,
    # which is harmless.
    pass
