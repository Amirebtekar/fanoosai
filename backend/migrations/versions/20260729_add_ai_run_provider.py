"""Record which provider returned a successful AI run."""

from alembic import op
import sqlalchemy as sa


revision = "20260729_ai_run_provider"
down_revision = "20260728_merge_parspak_brand"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("ai_runs", sa.Column("provider_used", sa.String(length=20), nullable=True))
    op.execute("UPDATE ai_runs SET provider_used = 'primary' WHERE status = 'success'")


def downgrade() -> None:
    op.drop_column("ai_runs", "provider_used")
