import importlib.util
from pathlib import Path


def test_organization_migration_backfills_projects_before_requiring_membership():
    path = Path(__file__).parents[1] / "migrations" / "versions" / "20260722_organizations.py"
    spec = importlib.util.spec_from_file_location("organizations_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)

    calls = []

    class Operations:
        def __getattr__(self, name):
            return lambda *args, **kwargs: calls.append((name, args, kwargs))

    migration.op = Operations()
    migration.upgrade()

    foreign_keys = [
        str(column.foreign_keys.pop().target_fullname)
        for name, args, _ in calls
        if name == "create_table"
        for column in args[1:]
        if getattr(column, "foreign_keys", None)
    ]
    assert "user.id" in foreign_keys
    assert "users.id" not in foreign_keys

    statements = [args[0] for name, args, _ in calls if name == "execute"]
    assert any("INSERT INTO organizations" in statement for statement in statements)
    assert any("INSERT INTO organization_members" in statement for statement in statements)
    assert any("UPDATE projects" in statement for statement in statements)
    add_index = next(i for i, (name, args, _) in enumerate(calls) if name == "add_column" and args[0] == "projects")
    required_index = next(i for i, (name, args, _) in enumerate(calls) if name == "alter_column" and args[0] == "projects")
    assert add_index < required_index
