"""Make merkur_documents.file_path nullable.

Reason: the inbox sync now scrapes the summary SPA directly instead of
downloading PDFs, so there is no local file for scraped-only documents.

Revision ID: 0005
Revises: 0004
"""
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("merkur_documents", "file_path", nullable=True)


def downgrade() -> None:
    # Re-set NOT NULL; any rows with NULL file_path must be fixed first.
    op.alter_column("merkur_documents", "file_path", nullable=False)
