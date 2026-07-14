from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Brand, RunBrand
from app.services.brand_extraction_service import ExtractionResult, ExtractedBrand


@dataclass(frozen=True)
class BrandPersistenceResult:
    brands: list[Brand]
    new_brands: int
    existing_brands: int
    run_brands: int


class BrandPersistenceService:
    """Persists extraction output only; identity matching remains replaceable."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def persist(self, ai_run_id: int, result: ExtractionResult) -> BrandPersistenceResult:
        saved: list[Brand] = []
        new_count = 0
        try:
            for extracted in result.brands:
                brand = await self._find(extracted)
                if brand is None:
                    brand = Brand(name=extracted.name, domain=extracted.domain)
                    self.session.add(brand)
                    await self.session.flush()
                    new_count += 1
                saved.append(brand)
                self.session.add(RunBrand(
                    ai_run_id=ai_run_id,
                    brand_id=brand.id,
                    raw_name=extracted.name,
                    rank=extracted.rank,
                    confidence=extracted.confidence,
                ))
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise
        return BrandPersistenceResult(saved, new_count, len(saved) - new_count, len(saved))

    async def _find(self, extracted: ExtractedBrand) -> Brand | None:
        field = Brand.domain if extracted.domain else Brand.name
        value = extracted.domain or extracted.name
        return (await self.session.execute(select(Brand).where(field == value))).scalar_one_or_none()
