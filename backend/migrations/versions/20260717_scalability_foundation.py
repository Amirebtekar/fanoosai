"""Add daily-run claims and high-volume lookup indexes."""

from alembic import op
import sqlalchemy as sa


revision = "20260717_scalability"
down_revision = "20250308_airun_extract"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE prompts ADD COLUMN IF NOT EXISTS last_run_at TIMESTAMPTZ")
    op.execute("UPDATE prompts SET last_run_at = (SELECT MAX(created_at) FROM ai_runs WHERE ai_runs.prompt_id = prompts.id)")
    op.execute("ALTER TABLE ai_runs ADD COLUMN IF NOT EXISTS archived_at TIMESTAMPTZ")
    op.execute("""
        CREATE TABLE IF NOT EXISTS daily_prompt_runs (
            id SERIAL PRIMARY KEY, prompt_id INTEGER NOT NULL REFERENCES prompts(id),
            ai_model_id INTEGER NOT NULL REFERENCES ai_models(id), run_date DATE NOT NULL,
            claimed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_daily_prompt_model_run UNIQUE(prompt_id, ai_model_id, run_date)
        )
    """)
    for statement in (
        "CREATE INDEX IF NOT EXISTS ix_daily_prompt_runs_date ON daily_prompt_runs(run_date)",
        "CREATE INDEX IF NOT EXISTS ix_projects_user_id ON projects(user_id)",
        "CREATE INDEX IF NOT EXISTS ix_prompts_project_id ON prompts(project_id)",
        "CREATE INDEX IF NOT EXISTS ix_ai_runs_prompt_created ON ai_runs(prompt_id, created_at)",
        "CREATE INDEX IF NOT EXISTS ix_ai_runs_model_created ON ai_runs(ai_model_id, created_at)",
        "CREATE INDEX IF NOT EXISTS ix_ai_runs_retention ON ai_runs(archived_at, created_at)",
        "CREATE INDEX IF NOT EXISTS ix_brands_name ON brands(name)",
    ):
        op.execute(statement)

    op.execute("""
        CREATE TABLE IF NOT EXISTS ai_runs_archive (
            id INTEGER NOT NULL, prompt_id INTEGER NOT NULL, ai_model_id INTEGER NOT NULL,
            request_text TEXT NOT NULL, response_text TEXT, status VARCHAR(20) NOT NULL,
            extraction_status VARCHAR(20) NOT NULL, processed_at TIMESTAMPTZ,
            error_message TEXT, created_at TIMESTAMPTZ NOT NULL, completed_at TIMESTAMPTZ,
            archived_at TIMESTAMPTZ NOT NULL
        ) PARTITION BY RANGE (created_at)
    """)
    op.execute("CREATE TABLE IF NOT EXISTS ai_runs_archive_default PARTITION OF ai_runs_archive DEFAULT")
    op.execute("""
        CREATE OR REPLACE FUNCTION archive_old_ai_runs(cutoff TIMESTAMPTZ)
        RETURNS INTEGER LANGUAGE plpgsql AS $$
        DECLARE moved INTEGER;
        BEGIN
            INSERT INTO ai_runs_archive
            SELECT id, prompt_id, ai_model_id, request_text, response_text, status,
                   extraction_status, processed_at, error_message, created_at,
                   completed_at, now()
            FROM ai_runs WHERE archived_at IS NULL AND created_at < cutoff;
            GET DIAGNOSTICS moved = ROW_COUNT;
            UPDATE ai_runs SET request_text = '[archived]', response_text = NULL,
                error_message = NULL, archived_at = now()
            WHERE archived_at IS NULL AND created_at < cutoff;
            RETURN moved;
        END $$
    """)


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS archive_old_ai_runs(TIMESTAMPTZ)")
    op.execute("DROP TABLE IF EXISTS ai_runs_archive_default")
    op.execute("DROP TABLE IF EXISTS ai_runs_archive")
    op.drop_column("prompts", "last_run_at")
    op.drop_index("ix_ai_runs_retention", table_name="ai_runs")
    op.drop_column("ai_runs", "archived_at")
    op.drop_index("ix_brands_name", table_name="brands")
    op.drop_index("ix_ai_runs_model_created", table_name="ai_runs")
    op.drop_index("ix_ai_runs_prompt_created", table_name="ai_runs")
    op.drop_index("ix_prompts_project_id", table_name="prompts")
    op.drop_index("ix_projects_user_id", table_name="projects")
    op.drop_index("ix_daily_prompt_runs_date", table_name="daily_prompt_runs")
    op.drop_table("daily_prompt_runs")
