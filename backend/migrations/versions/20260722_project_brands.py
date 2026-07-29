"""Add project-owned and competitor brands."""
from alembic import op
import sqlalchemy as sa

revision = "20260722_project_brands"
down_revision = "20260722_daily_source"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("project_brands", sa.Column("id", sa.Integer, primary_key=True), sa.Column("project_id", sa.Integer, sa.ForeignKey("projects.id"), nullable=False), sa.Column("name", sa.String(200), nullable=False), sa.Column("domain", sa.String(500)), sa.Column("kind", sa.String(20), nullable=False), sa.Column("brand_id", sa.Integer, sa.ForeignKey("brands.id")), sa.UniqueConstraint("project_id", "domain", name="uq_project_brand_domain"))

def downgrade():
    op.drop_table("project_brands")
