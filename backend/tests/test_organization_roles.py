import pytest

from app.repositories.project_repository import ProjectRepository


class Session:
    def __init__(self, role): self.role = role
    async def scalar(self, _): return self.role
    async def execute(self, _):
        class Result:
            def scalar_one_or_none(self): return object()
        return Result()


@pytest.mark.asyncio
async def test_viewer_cannot_write_project():
    assert not await ProjectRepository(Session("viewer")).can_write(1, 1)


@pytest.mark.asyncio
async def test_owner_admin_and_analyst_can_write_project():
    for role in ("owner", "admin", "analyst"):
        assert await ProjectRepository(Session(role)).can_write(1, 1)


@pytest.mark.asyncio
async def test_analyst_cannot_manage_project_settings_or_delete():
    assert not await ProjectRepository(Session("analyst")).can_manage_project(1, 1)


@pytest.mark.asyncio
async def test_only_owner_and_admin_can_manage_project():
    for role in ("owner", "admin"):
        assert await ProjectRepository(Session(role)).can_manage_project(1, 1)


@pytest.mark.asyncio
async def test_all_members_can_read_project():
    for role in ("owner", "admin", "analyst", "viewer"):
        assert await ProjectRepository(Session(role)).can_read(1, 1)
