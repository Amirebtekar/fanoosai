"""Allow abandoned daily-run claims to expire."""

from alembic import op
import sqlalchemy as sa


revision = "20260730_daily_run_status"
down_revision = "20260729_ai_run_provider"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "daily_prompt_runs",
        sa.Column("status", sa.String(length=20), nullable=False, server_default="completed"),
    )
    op.alter_column("daily_prompt_runs", "status", server_default=None)


def downgrade() -> None:
    op.drop_column("daily_prompt_runs", "status")
