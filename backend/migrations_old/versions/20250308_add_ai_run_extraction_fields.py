"""Add extraction fields to ai_runs.

Revision ID: 20250308_add_ai_run_extraction_fields
Revises: None
"""

from alembic import op
import sqlalchemy as sa


revision = "20250308_add_ai_run_extraction_fields"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "ai_runs",
        sa.Column(
            "extraction_status",
            sa.VARCHAR(length=20),
            nullable=True,
            server_default=sa.text("'pending'"),
        ),
    )
    op.add_column(
        "ai_runs",
        sa.Column("processed_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("ai_runs", "processed_at")
    op.drop_column("ai_runs", "extraction_status")
