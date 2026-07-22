"""Record whether a daily execution was manual or scheduled."""

from alembic import op
import sqlalchemy as sa


revision = "20260722_daily_source"
down_revision = "20260717_scalability"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "daily_prompt_runs",
        sa.Column("source", sa.String(length=20), nullable=False, server_default="scheduled"),
    )
    op.alter_column("daily_prompt_runs", "source", server_default=None)


def downgrade() -> None:
    op.drop_column("daily_prompt_runs", "source")
