import pytest

from app.repositories.project_repository import ProjectRepository


class FakeSession:
    def __init__(self, owned_brand=None):
        self.refreshed = None
        self.owned_brand = owned_brand

    async def scalar(self, _statement):
        return self.owned_brand

    async def commit(self):
        pass

    async def refresh(self, project):
        self.refreshed = project


@pytest.mark.asyncio
async def test_update_refreshes_project_before_returning():
    project = type("Project", (), {"name": "Old", "description": None})()
    session = FakeSession()

    updated = await ProjectRepository(session).update(project, name="New")

    assert updated.name == "New"
    assert session.refreshed is project


@pytest.mark.asyncio
async def test_domain_update_keeps_owned_brand_in_sync():
    owned_brand = type("Brand", (), {"domain": "old.example"})()
    project = type("Project", (), {
        "id": 3, "name": "Project", "description": None, "website_url": "old.example",
    })()
    session = FakeSession(owned_brand)

    await ProjectRepository(session).update(project, website_url="new.example")

    assert project.website_url == owned_brand.domain == "new.example"
