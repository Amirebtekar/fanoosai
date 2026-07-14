from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from app.core.config import settings

engine = create_async_engine(settings.DATABASE_URL, echo=False)
async_session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

async def get_async_session():
    async with async_session_maker() as session:
        yield session

async def create_db_and_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # ponytail: replace with Alembic migrations when schema changes become regular.
        await conn.execute(text("""
            WITH canonical AS (
                SELECT model_key, MIN(id) AS keep_id FROM ai_models GROUP BY model_key
            )
            UPDATE prompt_models pm
            SET ai_model_id = canonical.keep_id
            FROM ai_models old_model
            JOIN canonical ON canonical.model_key = old_model.model_key
            WHERE pm.ai_model_id = old_model.id AND old_model.id <> canonical.keep_id
        """))
        await conn.execute(text("""
            DELETE FROM prompt_models a
            USING prompt_models b
            WHERE a.id > b.id
              AND a.prompt_id = b.prompt_id
              AND a.ai_model_id = b.ai_model_id
        """))
        await conn.execute(text("""
            DELETE FROM ai_models a
            USING ai_models b
            WHERE a.id > b.id AND a.model_key = b.model_key
        """))
        await conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_ai_models_model_key ON ai_models (model_key)"))
        await conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_prompt_model ON prompt_models (prompt_id, ai_model_id)"))
