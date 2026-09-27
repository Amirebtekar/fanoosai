"""Add persistent brand aliases."""

from alembic import op
import sqlalchemy as sa


revision = "20260927_brand_aliases"
down_revision = "20260822_system_settings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "brand_aliases",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("brand_id", sa.Integer(), sa.ForeignKey("brands.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(200), nullable=True),
        sa.Column("normalized_name", sa.String(200), nullable=True, unique=True),
        sa.Column("domain", sa.String(500), nullable=True, unique=True),
        sa.Column("normalized_domain", sa.String(500), nullable=True, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("normalized_name IS NOT NULL OR normalized_domain IS NOT NULL", name="ck_brand_alias_identity"),
    )
    op.create_index("ix_brand_aliases_brand_id", "brand_aliases", ["brand_id"])


def downgrade() -> None:
    op.drop_index("ix_brand_aliases_brand_id", table_name="brand_aliases")
    op.drop_table("brand_aliases")
