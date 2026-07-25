import pytest

from app.repositories.project_repository import ProjectRepository


class FakeSession:
    def __init__(self):
        self.refreshed = None

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
