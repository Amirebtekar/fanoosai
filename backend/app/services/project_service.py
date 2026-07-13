import logging
from typing import List, Optional

from app.database.models import Project, UserTable
from app.repositories.project_repository import ProjectRepository
from app.repositories.user_repository import UserRepository

logger = logging.getLogger(__name__)

class ProjectService:
    def __init__(self, project_repo: ProjectRepository, user_repo: UserRepository):
        self.project_repo = project_repo
        self.user_repo = user_repo

    async def create_project(
        self, user_id: int, name: str, description: Optional[str] = None, website_url: Optional[str] = None
    ) -> Project:
        # Guard: Check if user is verified
        user = await self.user_repo.get_by_id(user_id)
        if not user or not user.is_verified:
            raise PermissionError("User is not verified. Verification required to create projects.")
        
        # Create project
        project = await self.project_repo.create(user_id=user_id, name=name, description=description, website_url=website_url)
        logger.info(f"Project created: {project.id} by user {user_id}")
        return project

    async def list_user_projects(self, user_id: int) -> List[Project]:
        return await self.project_repo.list_by_user(user_id=user_id)

    async def get_project(self, project_id: int, user_id: int) -> Project:
        project = await self.project_repo.get_by_id(project_id=project_id, user_id=user_id)
        if not project:
            raise ValueError("Project not found or access denied")
        return project

    async def update_project(self, project: Project, name: Optional[str] = None, description: Optional[str] = None, website_url: Optional[str] = None) -> Project:
        return await self.project_repo.update(project=project, name=name, description=description, website_url=website_url)

    async def delete_project(self, project: Project) -> None:
        await self.project_repo.delete(project=project)
