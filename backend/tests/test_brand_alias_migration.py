import importlib.util
from pathlib import Path


def test_brand_alias_migration_creates_unique_name_and_domain_mappings():
    path = Path(__file__).parents[1] / "migrations" / "versions" / "20260927_brand_aliases.py"
    spec = importlib.util.spec_from_file_location("brand_alias_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)

    calls = []

    class Operations:
        def __getattr__(self, name):
            return lambda *args, **kwargs: calls.append((name, args, kwargs))

    migration.op = Operations()
    migration.upgrade()

    create = next(args for name, args, _ in calls if name == "create_table")
    columns = {column.name: column for column in create[1:]}
    assert columns["brand_id"].foreign_keys
    assert columns["normalized_name"].unique
    assert columns["domain"].unique
    assert columns["normalized_domain"].unique
    assert columns["name"].nullable
    assert any(getattr(constraint, "name", None) == "ck_brand_alias_identity" for constraint in create[1:] if hasattr(constraint, "name"))
    assert any(name == "create_index" and args[0] == "ix_brand_aliases_brand_id" for name, args, _ in calls)
