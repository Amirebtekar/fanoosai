"""Require a domain for every brand."""

from alembic import op
import sqlalchemy as sa


revision = "20260728_require_brand_domain"
down_revision = "20260722_organizations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        UPDATE project_brands
        SET brand_id = NULL
        WHERE brand_id IN (SELECT id FROM brands WHERE domain IS NULL)
    """)
    op.execute("DELETE FROM run_brands WHERE brand_id IN (SELECT id FROM brands WHERE domain IS NULL)")
    op.execute("DELETE FROM brands WHERE domain IS NULL")
    op.alter_column("brands", "domain", existing_type=sa.String(length=500), nullable=False)


def downgrade() -> None:
    op.alter_column("brands", "domain", existing_type=sa.String(length=500), nullable=True)
