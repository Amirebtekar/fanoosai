from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.models import Project

class ProjectRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, user_id: int, name: str, description: str | None = None, website_url: str | None = None) -> Project:
        project = Project(user_id=user_id, name=name, description=description, website_url=website_url)
        self.session.add(project)
        await self.session.commit()
        return project

    async def get_by_id(self, project_id: int, user_id: int) -> Project | None:
        stmt = select(Project).where(Project.id == project_id, Project.user_id == user_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_user(self, user_id: int) -> list[Project]:
        stmt = select(Project).where(Project.user_id == user_id).order_by(Project.created_at.desc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def update(self, project: Project, name: str | None = None, description: str | None = None, website_url: str | None = None) -> Project:
        if name is not None:
            project.name = name
        if description is not None:
            project.description = description
        if website_url is not None:
            project.website_url = website_url
        await self.session.commit()
        return project

    async def delete(self, project: Project) -> None:
        await self.session.delete(project)
        await self.session.commit()