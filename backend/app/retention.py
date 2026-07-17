import asyncio
from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from app.core.config import settings
from app.database.connection import async_session_maker


async def archive_old_runs() -> int:
    cutoff = datetime.now(timezone.utc) - timedelta(days=settings.RUN_RETENTION_DAYS)
    async with async_session_maker() as session:
        result = await session.execute(text("SELECT archive_old_ai_runs(:cutoff)"), {"cutoff": cutoff})
        await session.commit()
        return int(result.scalar_one())


if __name__ == "__main__":
    print(asyncio.run(archive_old_runs()))
