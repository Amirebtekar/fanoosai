"""Track brand-extraction attempts and close out runs whose extraction already succeeded."""

from alembic import op
import sqlalchemy as sa

revision = "20261029_extraction_attempts"
down_revision = "20261019_daily_model_runs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "ai_runs",
        sa.Column("extraction_attempts", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index(
        "ix_ai_runs_extraction_retry",
        "ai_runs",
        ["extraction_status", "processed_at"],
        postgresql_where=sa.text("status = 'success' AND extraction_status = 'failed'"),
    )
    # The daily worker persisted brands but never marked extraction as completed.
    op.execute(
        """
        UPDATE ai_runs r
        SET extraction_status = 'completed', processed_at = COALESCE(r.processed_at, r.completed_at, r.created_at)
        WHERE r.status = 'success'
          AND r.extraction_status = 'pending'
          AND r.created_at < now() - interval '1 hour'
          AND EXISTS (SELECT 1 FROM run_brands rb WHERE rb.ai_run_id = r.id)
        """
    )
    # Stale pending runs without any stored brand are handed to the bounded retry.
    op.execute(
        """
        UPDATE ai_runs r
        SET extraction_status = 'failed', extraction_error = 'no brands recorded; queued for re-extraction'
        WHERE r.status = 'success'
          AND r.extraction_status = 'pending'
          AND r.created_at < now() - interval '1 hour'
          AND r.response_text IS NOT NULL
          AND NOT EXISTS (SELECT 1 FROM run_brands rb WHERE rb.ai_run_id = r.id)
        """
    )


def downgrade() -> None:
    op.drop_index("ix_ai_runs_extraction_retry", table_name="ai_runs")
    op.drop_column("ai_runs", "extraction_attempts")
