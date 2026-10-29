import logging
from dataclasses import dataclass

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Brand, BrandAlias, RunBrand
from app.services.brand_extraction_service import ExtractionResult, ExtractedBrand

logger = logging.getLogger(__name__)


def normalize_brand_name(value: str) -> str:
    return "".join(value.casefold().replace("\u200c", "").split())


def normalize_brand_domain(value: str) -> str:
    return value.strip().casefold().rstrip(".")


def resolve_brand_matches(name_match: Brand | None, domain_match: Brand | None) -> Brand | None:
    if name_match and domain_match and name_match.id != domain_match.id:
        raise ValueError("Brand name and domain resolve to different identities; admin review is required")
    return name_match or domain_match


def choose_brand_identity(name_matches: dict, domain_matches: dict):
    """Pick one brand for an extracted mention without failing the whole run.

    Returns ``(brand, reason)``. ``brand`` is None with reason ``"new"`` when nothing
    matches, or with reason ``"ambiguous"`` when the mention cannot be attributed
    safely. The official domain is the stronger identity signal, so it wins when
    the name points at a different brand.
    """
    if len(domain_matches) == 1:
        brand = next(iter(domain_matches.values()))
        if name_matches and brand.id not in name_matches:
            return brand, "domain_preferred"
        return brand, "matched"
    if len(domain_matches) > 1:
        shared = [brand_id for brand_id in domain_matches if brand_id in name_matches]
        if len(shared) == 1:
            return domain_matches[shared[0]], "matched"
        return None, "ambiguous"
    if len(name_matches) == 1:
        return next(iter(name_matches.values())), "matched"
    if len(name_matches) > 1:
        return None, "ambiguous"
    return None, "new"


async def acquire_brand_write_lock(session: AsyncSession) -> None:
    await session.execute(select(func.pg_advisory_xact_lock(734208914271)))


@dataclass(frozen=True)
class BrandPersistenceResult:
    brands: list[Brand]
    new_brands: int
    existing_brands: int
    run_brands: int
    skipped_brands: int = 0


class BrandPersistenceService:
    """Persists extraction output only; identity matching remains replaceable."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def persist(self, ai_run_id: int, result: ExtractionResult) -> BrandPersistenceResult:
        saved: list[Brand] = []
        links_by_brand: dict[int, RunBrand] = {}
        new_count = 0
        skipped = 0
        # A SAVEPOINT keeps a failure here from rolling back (and expiring) the
        # caller's objects; the caller can still record the failure afterwards.
        async with self.session.begin_nested():
            await acquire_brand_write_lock(self.session)
            # Re-extraction replaces the previous links of this run (idempotent retries).
            await self.session.execute(delete(RunBrand).where(RunBrand.ai_run_id == ai_run_id))
            for extracted in result.brands:
                if not extracted.domain:
                    continue
                brand, reason = await self._find(extracted)
                if reason == "ambiguous":
                    skipped += 1
                    logger.warning("brand_identity_ambiguous", extra={"event_data": {
                        "ai_run_id": ai_run_id, "name": extracted.name, "domain": extracted.domain,
                    }})
                    continue
                if reason == "domain_preferred":
                    logger.warning("brand_identity_conflict_domain_preferred", extra={"event_data": {
                        "ai_run_id": ai_run_id, "name": extracted.name, "domain": extracted.domain, "brand_id": brand.id,
                    }})
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
            await self.session.flush()
        await self.session.commit()
        return BrandPersistenceResult(saved, new_count, len(saved) - new_count, len(saved), skipped)

    async def _find(self, extracted: ExtractedBrand) -> tuple[Brand | None, str]:
        normalized_name = normalize_brand_name(extracted.name)
        normalized_domain = normalize_brand_domain(extracted.domain or "")
        with self.session.no_autoflush:
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
        match, reason = choose_brand_identity(name_matches, domain_matches)
        if match is None:
            return None, reason
        locked = (await self.session.execute(select(Brand).where(Brand.id == match.id).with_for_update())).scalar_one_or_none()
        if locked is None:
            return None, "new"
        return locked, reason
