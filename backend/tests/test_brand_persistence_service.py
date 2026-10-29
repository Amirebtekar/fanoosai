from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from app.services.brand_extraction_service import ExtractedBrand, ExtractionResult
from app.services.brand_persistence_service import (
    BrandPersistenceService,
    choose_brand_identity,
    normalize_brand_name,
    resolve_brand_matches,
)


class FakeResult:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value


class FakeNested:
    def __init__(self, session):
        self.session = session

    async def __aenter__(self):
        self.session.savepoints += 1
        self.snapshot = (list(self.session.brands), list(self.session.links))
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if exc_type is not None:
            self.session.brands, self.session.links = self.snapshot
            self.session.savepoint_rollbacks += 1
        return False


class FakeSession:
    def __init__(self):
        self.brands = []
        self.links = []
        self.added = []
        self.committed = False
        self.rolled_back = False
        self.savepoints = 0
        self.savepoint_rollbacks = 0
        self.deleted_run_ids = []

    def begin_nested(self):
        return FakeNested(self)

    @property
    @contextmanager
    def no_autoflush(self):
        yield

    async def execute(self, statement):
        if statement.__class__.__name__ == "Delete":
            run_id = next(iter(statement.compile().params.values()))
            self.deleted_run_ids.append(run_id)
            self.links = [link for link in self.links if link.ai_run_id != run_id]
            return FakeResult(None)
        values = set(statement.compile().params.values())
        return FakeResult(next((b for b in self.brands if b.id in values or b.domain in values or normalize_brand_name(b.name) in values), None))

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


def brand(brand_id, name="x", domain="x.com"):
    return SimpleNamespace(id=brand_id, name=name, domain=domain)


def test_brand_identity_resolution_rejects_conflicting_name_and_domain_matches():
    named = type("BrandRecord", (), {"id": 1})()
    domain = type("BrandRecord", (), {"id": 2})()

    with pytest.raises(ValueError, match="different identities"):
        resolve_brand_matches(named, domain)


def test_brand_identity_resolution_uses_the_domain_when_name_is_unmatched():
    domain = type("BrandRecord", (), {"id": 2})()

    assert resolve_brand_matches(None, domain) is domain


def test_choose_identity_prefers_domain_when_name_points_to_another_brand():
    by_domain, by_name = brand(1), brand(333)

    chosen, reason = choose_brand_identity({333: by_name}, {1: by_domain})

    assert chosen is by_domain
    assert reason == "domain_preferred"


def test_choose_identity_matches_when_name_and_domain_agree():
    same = brand(5)

    assert choose_brand_identity({5: same}, {5: same}) == (same, "matched")


def test_choose_identity_uses_name_when_domain_is_unknown():
    named = brand(7)

    assert choose_brand_identity({7: named}, {}) == (named, "matched")


def test_choose_identity_is_new_when_nothing_matches():
    assert choose_brand_identity({}, {}) == (None, "new")


def test_choose_identity_is_ambiguous_for_two_domain_matches_without_a_name_tiebreak():
    assert choose_brand_identity({}, {1: brand(1), 2: brand(2)}) == (None, "ambiguous")


def test_choose_identity_breaks_domain_tie_with_the_name():
    first, second = brand(1), brand(2)

    assert choose_brand_identity({2: second}, {1: first, 2: second}) == (second, "matched")


def test_choose_identity_is_ambiguous_for_two_name_matches_without_a_domain():
    assert choose_brand_identity({1: brand(1), 2: brand(2)}, {}) == (None, "ambiguous")


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
    assert session.savepoints == 1


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
async def test_collapses_duplicate_aliases_in_a_single_run_to_one_best_rank_link():
    session = FakeSession()
    result = await BrandPersistenceService(session).persist(7, ExtractionResult([
        ExtractedBrand(1, "پارس‌پک", "parspack.com", 0.99),
        ExtractedBrand(2, "پارس پک", "parspak.com", 0.95),
    ]))

    assert result.new_brands == 1
    assert result.run_brands == 1
    assert len(session.links) == 1
    assert session.links[0].rank == 1
    assert session.links[0].raw_name == "پارس‌پک"


@pytest.mark.asyncio
async def test_rolls_back_only_the_savepoint_when_persistence_fails():
    class FailingSession(FakeSession):
        def add(self, entity):
            raise RuntimeError("db failure")

    session = FailingSession()
    with pytest.raises(RuntimeError):
        await BrandPersistenceService(session).persist(7, ExtractionResult([
            ExtractedBrand(1, "Parspack", "parspack.com", 0.99),
        ]))
    assert session.savepoint_rollbacks == 1
    assert not session.committed


@pytest.mark.asyncio
async def test_a_name_and_domain_conflict_keeps_the_rest_of_the_run():
    """Regression: one conflicting brand used to drop every brand of the run."""
    session = FakeSession()
    service = BrandPersistenceService(session)

    parspack = brand(1001, "پارس‌پک", "parspack.com")

    async def fake_find(extracted):
        if extracted.name == "ParsPack":
            return parspack, "domain_preferred"
        if extracted.name == "Mystery":
            return None, "ambiguous"
        return None, "new"

    service._find = fake_find
    result = await service.persist(2675, ExtractionResult([
        ExtractedBrand(1, "ArvanCloud", "arvancloud.ir", 1.0),
        ExtractedBrand(2, "Mystery", "mystery.ir", 1.0),
        ExtractedBrand(3, "ParsPack", "parspack.com", 1.0),
    ]))

    assert result.run_brands == 2
    assert result.skipped_brands == 1
    assert {link.raw_name: link.rank for link in session.links} == {"ArvanCloud": 1, "ParsPack": 3}
    assert next(link for link in session.links if link.raw_name == "ParsPack").brand_id == 1001
    assert session.committed


@pytest.mark.asyncio
async def test_re_extracting_a_run_replaces_its_previous_links():
    session = FakeSession()
    service = BrandPersistenceService(session)
    extraction = ExtractionResult([ExtractedBrand(1, "Derak Cloud", "derak.cloud", 1.0)])

    await service.persist(2672, extraction)
    await service.persist(2672, extraction)

    assert session.deleted_run_ids == [2672, 2672]
    assert len([link for link in session.links if link.ai_run_id == 2672]) == 1
