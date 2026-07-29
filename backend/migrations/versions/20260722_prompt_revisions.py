"""Add immutable prompt revisions."""
from alembic import op
import sqlalchemy as sa
revision = "20260722_prompt_revisions"
down_revision = "20260722_report_shares"
branch_labels = None
depends_on = None
def upgrade(): op.create_table("prompt_revisions", sa.Column("id", sa.Integer, primary_key=True), sa.Column("prompt_id", sa.Integer, sa.ForeignKey("prompts.id"), nullable=False), sa.Column("revision", sa.Integer, nullable=False), sa.Column("text", sa.Text, nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.UniqueConstraint("prompt_id", "revision", name="uq_prompt_revision"))
def downgrade(): op.drop_table("prompt_revisions")
