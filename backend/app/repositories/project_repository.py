from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.models import Project, ProjectBrand, Organization, OrganizationMember, Prompt, PromptModel

class ProjectRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, user_id: int, name: str, description: str | None = None, website_url: str | None = None, brand_name: str = "", organization_id: int | None = None) -> Project:
        if organization_id is not None:
            role = await self.session.scalar(select(OrganizationMember.role).where(OrganizationMember.organization_id == organization_id, OrganizationMember.user_id == user_id))
            if role not in {"owner", "admin", "analyst"}:
                raise PermissionError("Write role required for organization")
        else:
            organization_id = await self.session.scalar(select(Organization.id).where(Organization.owner_id == user_id))
        if organization_id is None:
            organization = Organization(name="Personal organization", owner_id=user_id); self.session.add(organization); await self.session.flush(); self.session.add(OrganizationMember(organization_id=organization.id, user_id=user_id, role="owner")); organization_id = organization.id
        project = Project(user_id=user_id, organization_id=organization_id, name=name, description=description, website_url=website_url)
        self.session.add(project)
        await self.session.flush()
        self.session.add(ProjectBrand(project_id=project.id, name=brand_name, domain=website_url, kind="owned"))
        await self.session.commit()
        return project

    async def get_by_website_url(self, website_url: str) -> Project | None:
        return await self.session.scalar(select(Project).where(Project.website_url == website_url))

    async def get_by_id(self, project_id: int, user_id: int | None = None) -> Project | None:
        stmt = select(Project).where(Project.id == project_id)
        if user_id is not None:
            stmt = stmt.join(OrganizationMember, OrganizationMember.organization_id == Project.organization_id).where(OrganizationMember.user_id == user_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_user(self, user_id: int) -> list[tuple[Project, int, int]]:
        stmt = select(Project, func.count(func.distinct(Prompt.id)), func.count(PromptModel.id)).join(OrganizationMember, OrganizationMember.organization_id == Project.organization_id).outerjoin(Prompt, and_(Prompt.project_id == Project.id, Prompt.is_active.is_(True))).outerjoin(PromptModel, PromptModel.prompt_id == Prompt.id).where(OrganizationMember.user_id == user_id).group_by(Project.id).order_by(Project.created_at.desc())
        result = await self.session.execute(stmt)
        return [(project, prompt_count, model_count) for project, prompt_count, model_count in result.all()]

    async def update(
        self, project: Project, name: str | None = None,
        description: str | None = None, website_url: str | None = None,
    ) -> Project:
        if name is not None:
            project.name = name
        if description is not None:
            project.description = description
        if website_url is not None:
            project.website_url = website_url
            owned_brand = await self.session.scalar(
                select(ProjectBrand).where(
                    ProjectBrand.project_id == project.id,
                    ProjectBrand.kind == "owned",
                )
            )
            if owned_brand is not None:
                owned_brand.domain = website_url
        await self.session.commit()
        await self.session.refresh(project)
        return project

    async def delete(self, project: Project) -> None:
        from app.database.models import (
            AIRun, Alert, AlertRule, DailyPromptRun, Prompt, PromptModel, ReportShare, RunBrand,
        )
        from sqlalchemy import delete as sa_delete

        prompt_ids = list((await self.session.scalars(select(Prompt.id).where(Prompt.project_id == project.id))).all())
        if prompt_ids:
            run_ids = list((await self.session.scalars(select(AIRun.id).where(AIRun.prompt_id.in_(prompt_ids)))).all())
            if run_ids:
                await self.session.execute(sa_delete(RunBrand).where(RunBrand.ai_run_id.in_(run_ids)))
            await self.session.execute(sa_delete(AIRun).where(AIRun.prompt_id.in_(prompt_ids)))
            await self.session.execute(sa_delete(PromptModel).where(PromptModel.prompt_id.in_(prompt_ids)))
            await self.session.execute(sa_delete(DailyPromptRun).where(DailyPromptRun.prompt_id.in_(prompt_ids)))
        await self.session.execute(sa_delete(ReportShare).where(ReportShare.project_id == project.id))
        await self.session.execute(sa_delete(Alert).where(Alert.project_id == project.id))
        await self.session.execute(sa_delete(AlertRule).where(AlertRule.project_id == project.id))
        if prompt_ids:
            await self.session.execute(sa_delete(Prompt).where(Prompt.id.in_(prompt_ids)))
        await self.session.execute(sa_delete(ProjectBrand).where(ProjectBrand.project_id == project.id))
        await self.session.execute(sa_delete(Project).where(Project.id == project.id))
        await self.session.commit()

    async def can_write(self, project_id: int, user_id: int) -> bool:
        role = await self.session.scalar(select(OrganizationMember.role).join(Project, Project.organization_id == OrganizationMember.organization_id).where(Project.id == project_id, OrganizationMember.user_id == user_id))
        return role in {"owner", "admin", "analyst"}

    async def can_read(self, project_id: int, user_id: int) -> bool:
        return await self.get_by_id(project_id, user_id) is not None

    async def can_manage_project(self, project_id: int, user_id: int) -> bool:
        role = await self.session.scalar(select(OrganizationMember.role).join(Project, Project.organization_id == OrganizationMember.organization_id).where(Project.id == project_id, OrganizationMember.user_id == user_id))
        return role in {"owner", "admin"}
