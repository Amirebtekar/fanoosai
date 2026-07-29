import pytest

from app.services.brand_extraction_service import ExtractedBrand, ExtractionResult
from app.services.brand_persistence_service import BrandPersistenceService, normalize_brand_name


class FakeResult:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value


class FakeSession:
    def __init__(self):
        self.brands = []
        self.links = []
        self.added = []
        self.committed = False
        self.rolled_back = False

    async def execute(self, statement):
        values = set(statement.compile().params.values())
        return FakeResult(next((b for b in self.brands if b.domain in values or normalize_brand_name(b.name) in values), None))

    def add(self, entity):
        self.added.append(entity)
        if entity.__class__.__name__ == "Brand":
            entity.id = len(self.brands) + 1
            self.brands.append(entity)
        else:
            self.links.append(entity)

    async def flush(self):
        pass

    async def commit(self):
        self.committed = True

    async def rollback(self):
        self.rolled_back = True


@pytest.mark.asyncio
async def test_persists_existing_or_new_brands_and_run_links():
    session = FakeSession()
    result = await BrandPersistenceService(session).persist(7, ExtractionResult([
        ExtractedBrand(1, "Parspack", "parspack.com", 0.99),
        ExtractedBrand(2, "Example", None, 0.8),
    ]))

    assert result.new_brands == 1
    assert result.existing_brands == 0
    assert result.run_brands == 1
    assert [brand.domain for brand in result.brands] == ["parspack.com"]
    assert session.committed


@pytest.mark.asyncio
async def test_reuses_a_brand_by_domain_when_its_name_changes():
    session = FakeSession()
    service = BrandPersistenceService(session)
    first = await service.persist(7, ExtractionResult([
        ExtractedBrand(1, "ابر آروان", "arvancloud.ir", 0.99),
    ]))
    second = await service.persist(8, ExtractionResult([
        ExtractedBrand(1, "آروان‌کلاد", "arvancloud.ir", 0.99),
    ]))

    assert second.new_brands == 0
    assert second.brands[0].id == first.brands[0].id


@pytest.mark.asyncio
async def test_reuses_a_brand_when_the_extracted_domain_is_misspelled():
    session = FakeSession()
    service = BrandPersistenceService(session)
    first = await service.persist(7, ExtractionResult([
        ExtractedBrand(2, "پارس‌پک", "parspack.com", 0.99),
    ]))
    second = await service.persist(8, ExtractionResult([
        ExtractedBrand(2, "پارس پک", "parspak.com", 0.99),
    ]))

    assert second.new_brands == 0
    assert second.brands[0].id == first.brands[0].id


@pytest.mark.asyncio
async def test_rolls_back_when_persistence_fails():
    class FailingSession(FakeSession):
        def add(self, entity):
            raise RuntimeError("db failure")

    session = FailingSession()
    with pytest.raises(RuntimeError):
        await BrandPersistenceService(session).persist(7, ExtractionResult([
            ExtractedBrand(1, "Parspack", "parspack.com", 0.99),
        ]))
    assert session.rolled_back
