from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Brand, RunBrand
from app.services.brand_extraction_service import ExtractionResult, ExtractedBrand


def normalize_brand_name(value: str) -> str:
    return "".join(value.casefold().replace("\u200c", "").split())


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
                if not extracted.domain:
                    continue
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
        normalized_name = normalize_brand_name(extracted.name)
        by_name = (await self.session.execute(
            select(Brand).where(
                func.replace(func.replace(func.lower(Brand.name), " ", ""), "\u200c", "") == normalized_name
            ).order_by(Brand.id).limit(1)
        )).scalar_one_or_none()
        if by_name is not None:
            return by_name
        return (await self.session.execute(
            select(Brand).where(Brand.domain == extracted.domain)
        )).scalar_one_or_none()
