"""Add error_provider, error_status, error_retryable, extraction_error to ai_runs."""

from alembic import op
import sqlalchemy as sa

revision = "20261018_ai_run_error_fields"
down_revision = "20260927_brand_aliases"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("ai_runs", sa.Column("error_provider", sa.String(20), nullable=True))
    op.add_column("ai_runs", sa.Column("error_status", sa.Integer(), nullable=True))
    op.add_column("ai_runs", sa.Column("error_retryable", sa.Boolean(), nullable=True))
    op.add_column("ai_runs", sa.Column("extraction_error", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("ai_runs", "extraction_error")
    op.drop_column("ai_runs", "error_retryable")
    op.drop_column("ai_runs", "error_status")
    op.drop_column("ai_runs", "error_provider")
