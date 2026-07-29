"""Add revocable report shares."""
from alembic import op
import sqlalchemy as sa
revision = "20260722_report_shares"
down_revision = "20260722_alerts"
branch_labels = None
depends_on = None
def upgrade(): op.create_table("report_shares", sa.Column("id", sa.Integer, primary_key=True), sa.Column("project_id", sa.Integer, sa.ForeignKey("projects.id"), nullable=False), sa.Column("token", sa.String(64), unique=True, nullable=False), sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False), sa.Column("revoked_at", sa.DateTime(timezone=True)))
def downgrade(): op.drop_table("report_shares")
