"""Merge the late parspak.com duplicate into parspack.com."""

from alembic import op


revision = "20260730_remerge_parspak_brand"
down_revision = "20260730_daily_run_status"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        DO $$
        DECLARE correct_id integer; wrong_id integer;
        BEGIN
            SELECT id INTO correct_id FROM brands WHERE domain = 'parspack.com';
            SELECT id INTO wrong_id FROM brands WHERE domain = 'parspak.com';
            IF correct_id IS NOT NULL AND wrong_id IS NOT NULL THEN
                DELETE FROM run_brands wrong
                USING run_brands correct
                WHERE wrong.brand_id = wrong_id
                  AND correct.brand_id = correct_id
                  AND correct.ai_run_id = wrong.ai_run_id;
                UPDATE run_brands SET brand_id = correct_id WHERE brand_id = wrong_id;
                UPDATE project_brands SET brand_id = correct_id WHERE brand_id = wrong_id;
                DELETE FROM brands WHERE id = wrong_id;
            END IF;
        END $$;
    """)


def downgrade() -> None:
    pass
