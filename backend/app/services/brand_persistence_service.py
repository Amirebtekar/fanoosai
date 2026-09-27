from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Brand, BrandAlias, RunBrand
from app.services.brand_extraction_service import ExtractionResult, ExtractedBrand


def normalize_brand_name(value: str) -> str:
    return "".join(value.casefold().replace("\u200c", "").split())


def normalize_brand_domain(value: str) -> str:
    return value.strip().casefold().rstrip(".")


def resolve_brand_matches(name_match: Brand | None, domain_match: Brand | None) -> Brand | None:
    if name_match and domain_match and name_match.id != domain_match.id:
        raise ValueError("Brand name and domain resolve to different identities; admin review is required")
    return name_match or domain_match


async def acquire_brand_write_lock(session: AsyncSession) -> None:
    await session.execute(select(func.pg_advisory_xact_lock(734208914271)))


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
        links_by_brand: dict[int, RunBrand] = {}
        new_count = 0
        try:
            await acquire_brand_write_lock(self.session)
            for extracted in result.brands:
                if not extracted.domain:
                    continue
                brand = await self._find(extracted)
                if brand is None:
                    brand = Brand(name=extracted.name, domain=extracted.domain)
                    self.session.add(brand)
                    await self.session.flush()
                    new_count += 1
                existing_link = links_by_brand.get(brand.id)
                if existing_link is not None:
                    existing_link.rank = min(existing_link.rank, extracted.rank)
                    if extracted.confidence is not None:
                        existing_link.confidence = max(existing_link.confidence or 0, extracted.confidence)
                    continue
                saved.append(brand)
                link = RunBrand(
                    ai_run_id=ai_run_id,
                    brand_id=brand.id,
                    raw_name=extracted.name,
                    rank=extracted.rank,
                    confidence=extracted.confidence,
                )
                links_by_brand[brand.id] = link
                self.session.add(link)
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise
        return BrandPersistenceResult(saved, new_count, len(saved) - new_count, len(saved))

    async def _find(self, extracted: ExtractedBrand, retry: bool = True) -> Brand | None:
        normalized_name = normalize_brand_name(extracted.name)
        normalized_domain = normalize_brand_domain(extracted.domain or "")
        name_alias = (await self.session.execute(
            select(Brand).join(BrandAlias).where(BrandAlias.normalized_name == normalized_name)
        )).scalar_one_or_none()
        name_match = (await self.session.execute(
            select(Brand).where(
                func.replace(func.replace(func.lower(Brand.name), " ", ""), "\u200c", "") == normalized_name
            ).order_by(Brand.id).limit(1)
        )).scalar_one_or_none()
        domain_alias = (await self.session.execute(
            select(Brand).join(BrandAlias).where(BrandAlias.normalized_domain == normalized_domain)
        )).scalar_one_or_none()
        domain_match = (await self.session.execute(
            select(Brand).where(func.rtrim(func.lower(Brand.domain), ".") == normalized_domain)
        )).scalar_one_or_none()

        name_matches = {brand.id: brand for brand in (name_alias, name_match) if brand is not None}
        domain_matches = {brand.id: brand for brand in (domain_alias, domain_match) if brand is not None}
        try:
            if len(name_matches) > 1 or len(domain_matches) > 1:
                raise ValueError("Brand identity is ambiguous; admin review is required")
            match = resolve_brand_matches(next(iter(name_matches.values()), None), next(iter(domain_matches.values()), None))
        except ValueError:
            if retry:
                return await self._find(extracted, retry=False)
            raise
        if match is None:
            return None
        locked = (await self.session.execute(select(Brand).where(Brand.id == match.id).with_for_update())).scalar_one_or_none()
        return locked if locked is not None else await self._find(extracted, retry=False)
