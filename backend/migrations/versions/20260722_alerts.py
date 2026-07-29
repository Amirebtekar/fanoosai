"""Add project alert rules and inbox."""
from alembic import op
import sqlalchemy as sa
revision = "20260722_alerts"
down_revision = "20260722_project_brands"
branch_labels = None
depends_on = None
def upgrade():
    op.create_table("alert_rules", sa.Column("id", sa.Integer, primary_key=True), sa.Column("project_id", sa.Integer, sa.ForeignKey("projects.id"), nullable=False), sa.Column("kind", sa.String(30), nullable=False), sa.Column("cooldown_hours", sa.Integer, nullable=False, server_default="24"), sa.Column("last_triggered_at", sa.DateTime(timezone=True)))
    op.create_table("alerts", sa.Column("id", sa.Integer, primary_key=True), sa.Column("project_id", sa.Integer, sa.ForeignKey("projects.id"), nullable=False), sa.Column("kind", sa.String(30), nullable=False), sa.Column("message", sa.Text, nullable=False), sa.Column("read_at", sa.DateTime(timezone=True)), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
def downgrade():
    op.drop_table("alerts"); op.drop_table("alert_rules")
