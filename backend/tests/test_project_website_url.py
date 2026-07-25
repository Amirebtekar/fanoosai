import pytest
from pydantic import ValidationError

from app.projects.schema import ProjectCreate
from app.services.project_service import ProjectService


def test_project_website_url_is_required_and_normalized_to_domain():
    with pytest.raises(ValidationError):
        ProjectCreate(name="Project")

    project = ProjectCreate(name="Project", website_url="HTTPS://www.Site.com/path", brand_name="Fanoos")

    assert project.website_url == "site.com"


def test_project_requires_an_owned_brand_name():
    with pytest.raises(ValidationError):
        ProjectCreate(name="Project", website_url="site.com")

    project = ProjectCreate(name="Project", website_url="site.com", brand_name="  Fanoos  ")

    assert project.brand_name == "Fanoos"


class VerifiedUserRepository:
    async def get_by_id(self, user_id):
        return type("User", (), {"is_verified": True})()


class DuplicateWebsiteProjectRepository:
    async def get_by_website_url(self, website_url):
        return object()


class ProjectRepository:
    async def get_by_website_url(self, website_url):
        return None

    async def create(self, **kwargs):
        self.project_data = kwargs
        return type("Project", (), {"id": 1})()


@pytest.mark.asyncio
async def test_duplicate_website_domain_is_rejected():
    service = ProjectService(DuplicateWebsiteProjectRepository(), VerifiedUserRepository())

    with pytest.raises(ValueError, match="website domain already exists"):
        await service.create_project(user_id=1, name="Other project", website_url="site.com")


@pytest.mark.asyncio
async def test_owned_brand_is_created_with_project():
    repository = ProjectRepository()
    service = ProjectService(repository, VerifiedUserRepository())

    await service.create_project(user_id=1, name="Project", website_url="site.com", brand_name="Fanoos")

    assert repository.project_data["brand_name"] == "Fanoos"
