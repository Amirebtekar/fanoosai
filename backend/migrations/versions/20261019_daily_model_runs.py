"""Create daily_model_runs table for per-model daily execution state."""

from alembic import op
import sqlalchemy as sa

revision = "20261019_daily_model_runs"
down_revision = "20261018_ai_run_error_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "daily_model_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("prompt_id", sa.Integer(), sa.ForeignKey("prompts.id"), nullable=False),
        sa.Column("model", sa.String(200), nullable=False),
        sa.Column("run_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="4"),
        sa.Column("last_error_message", sa.Text(), nullable=True),
        sa.Column("last_error_provider", sa.String(20), nullable=True),
        sa.Column("last_error_status", sa.Integer(), nullable=True),
        sa.Column("last_error_retryable", sa.Boolean(), nullable=True),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("success_run_id", sa.Integer(), sa.ForeignKey("ai_runs.id"), nullable=True),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("prompt_id", "model", "run_date", name="uq_daily_model_run"),
    )
    op.create_index("ix_daily_model_runs_date", "daily_model_runs", ["run_date"])
    op.create_index("ix_daily_model_runs_prompt_date", "daily_model_runs", ["prompt_id", "run_date"])


def downgrade() -> None:
    op.drop_index("ix_daily_model_runs_prompt_date", "daily_model_runs")
    op.drop_index("ix_daily_model_runs_date", "daily_model_runs")
    op.drop_table("daily_model_runs")
