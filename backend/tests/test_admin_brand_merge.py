from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy.dialects import postgresql

import app.admin.router as admin_router
from app.database.models import Brand, BrandAlias
from app.services.brand_persistence_service import normalize_brand_name


class AliasRows:
    def __init__(self, values):
        self.values = values

    def scalars(self):
        return self

    def all(self):
        return self.values


class AliasSession:
    def __init__(self, aliases):
        self.aliases = aliases

    async def execute(self, statement):
        return AliasRows(self.aliases)


def test_brand_merge_endpoints_require_superuser():
    routes = {route.path: route for route in admin_router.router.routes if "brands" in route.path}
    expected = {
        "/admin/brands": "GET",
        "/admin/brands/merge-preview": "POST",
        "/admin/brands/merge": "POST",
    }
    for path, method in expected.items():
        route = routes[path]
        assert method in route.methods
        assert any(dependency.call is admin_router.require_superuser for dependency in route.dependant.dependencies)


def test_brand_merge_preview_schema_exposes_all_impact_counts():
    assert set(admin_router.BrandMergePreview.model_fields) == {
        "canonical",
        "sources",
        "conflicts",
        "run_links_to_move",
        "project_links_to_repoint",
        "aliases_to_preserve",
        "duplicate_run_links_to_remove",
    }


def test_merge_keeps_best_rank_and_prefers_canonical_on_ties():
    query = admin_router._ranked_run_brand_links(5, [5, 8, 9])
    sql = str(query.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))

    assert "row_number() OVER (PARTITION BY run_brands.ai_run_id" in sql
    assert "run_brands.rank, CASE WHEN (run_brands.brand_id = 5) THEN 0 ELSE 1 END" in sql
    assert "run_brands.id" in sql


def test_merge_detects_alias_name_conflicts_with_unselected_brands():
    canonical = Brand(id=1, name="برند اصلی", domain="canonical.example")
    source = Brand(id=2, name="پارس‌پک", domain="parspack.com")
    outsider = Brand(id=3, name="پارس پک", domain="another.example")

    conflicts = admin_router._brand_alias_conflicts(canonical, [source], [outsider], [])

    assert conflicts == ["نام «پارس‌پک» از قبل به برند دیگری متصل است"]


def test_brand_alias_table_has_unique_normalized_names_and_domains():
    assert BrandAlias.__table__.c.normalized_name.unique
    assert BrandAlias.__table__.c.domain.unique
    assert BrandAlias.__table__.c.normalized_domain.unique
    assert next(iter(BrandAlias.__table__.c.brand_id.foreign_keys)).target_fullname == "brands.id"


@pytest.mark.asyncio
async def test_alias_preview_counts_unique_names_and_domains_excluding_canonical():
    canonical = Brand(id=1, name="پارس‌پک", domain="parspack.com")
    source_a = Brand(id=2, name="پارسیپک", domain="parsipak.ir")
    source_b = Brand(id=3, name="پارسپاک", domain="pars-pak.ir")
    aliases = [
        BrandAlias(id=1, brand_id=2, name="پارسیپک", normalized_name=normalize_brand_name("پارسیپک")),
        BrandAlias(id=2, brand_id=2, domain="parsipak.ir"),
        BrandAlias(id=3, brand_id=3, name="پارسپاک", normalized_name=normalize_brand_name("پارسپاک")),
        BrandAlias(id=4, brand_id=1, name="پارس پک", normalized_name=normalize_brand_name("پارس پک")),
        BrandAlias(id=5, brand_id=1, domain="parspack.com"),
    ]

    count = await admin_router._alias_merge_count(AliasSession(aliases), canonical, [source_a, source_b])

    assert count == 4


@pytest.mark.asyncio
async def test_merge_rejects_canonical_brand_in_source_ids_before_database_access():
    class NeverCalled:
        async def execute(self, statement):
            raise AssertionError("invalid selections must be rejected before querying")

    with pytest.raises(HTTPException) as error:
        await admin_router._selected_brands(
            NeverCalled(),
            admin_router.BrandMergeRequest(canonical_id=4, source_ids=[4]),
        )

    assert error.value.status_code == 422
