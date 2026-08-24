import time
from typing import Dict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import SystemSetting

CACHE_TTL_SECONDS = 30

EXTRACTION_PROMPT_KEY = "extraction_prompt"
EXTRACTION_MODEL_KEY = "extraction_model"
DOMAIN_INSTRUCTION_KEY = "domain_format_instruction"


class SystemSettingsRepository:
    """Key/value store for runtime-editable system settings with a small TTL cache."""

    _cache: Dict[str, tuple[float, str]] = {}

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, key: str) -> str | None:
        cached = self._cache.get(key)
        if cached and time.monotonic() - cached[0] < CACHE_TTL_SECONDS:
            return cached[1]
        value = (await self.session.execute(
            select(SystemSetting.value).where(SystemSetting.key == key)
        )).scalar_one_or_none()
        if value is not None:
            self._cache[key] = (time.monotonic(), value)
        return value

    async def set(self, key: str, value: str) -> None:
        setting = await self.session.get(SystemSetting, key)
        if setting is None:
            self.session.add(SystemSetting(key=key, value=value))
        else:
            setting.value = value
        await self.session.commit()
        self._cache[key] = (time.monotonic(), value)


async def get_setting(session: AsyncSession, key: str, default: str) -> str:
    value = await SystemSettingsRepository(session).get(key)
    return value if value not in (None, "") else default
