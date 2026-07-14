import pytest

from app.services.brand_extraction_service import ExtractedBrand, ExtractionResult
from app.services.brand_persistence_service import BrandPersistenceService


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
        params = statement.compile().params
        value = params.get("domain") or params.get("name")
        return FakeResult(next((b for b in self.brands if (b.domain or b.name) == value), None))

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

    assert result.new_brands == 2
    assert result.existing_brands == 0
    assert result.run_brands == 2
    assert session.committed


@pytest.mark.asyncio
async def test_rolls_back_when_persistence_fails():
    class FailingSession(FakeSession):
        def add(self, entity):
            raise RuntimeError("db failure")

    session = FailingSession()
    with pytest.raises(RuntimeError):
        await BrandPersistenceService(session).persist(7, ExtractionResult([]))
    assert session.rolled_back
