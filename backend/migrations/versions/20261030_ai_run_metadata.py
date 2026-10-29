"""Store token details, cost and web-search metadata for each AI run."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "20261030_ai_run_metadata"
down_revision = "20261029_extraction_attempts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("ai_runs", sa.Column("reasoning_tokens", sa.Integer(), nullable=True))
    op.add_column("ai_runs", sa.Column("cached_tokens", sa.Integer(), nullable=True))
    op.add_column("ai_runs", sa.Column("web_search_count", sa.Integer(), nullable=True))
    op.add_column("ai_runs", sa.Column("cost_usd", sa.Float(), nullable=True))
    op.add_column("ai_runs", sa.Column("web_search_queries", JSONB(), nullable=True))
    op.add_column("ai_runs", sa.Column("web_search_actions", JSONB(), nullable=True))
    op.add_column("ai_runs", sa.Column("citations", JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("ai_runs", "citations")
    op.drop_column("ai_runs", "web_search_actions")
    op.drop_column("ai_runs", "web_search_queries")
    op.drop_column("ai_runs", "cost_usd")
    op.drop_column("ai_runs", "web_search_count")
    op.drop_column("ai_runs", "cached_tokens")
    op.drop_column("ai_runs", "reasoning_tokens")
