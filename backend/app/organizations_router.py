from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.dependencies import get_session
from app.auth.fastapi_users import fastapi_users
from app.database.models import Organization, OrganizationMember, UserTable

router = APIRouter(prefix="/organizations", tags=["organizations"])

ROLES = {"owner", "admin", "analyst", "viewer"}

class OrganizationCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)

class MembershipCreate(BaseModel):
    user_id: int = Field(gt=0)
    role: str

@router.post("")
async def create(data: OrganizationCreate, session: AsyncSession = Depends(get_session), user: UserTable = Depends(fastapi_users.current_user())):
    org = Organization(name=data.name, owner_id=user.id); session.add(org); await session.flush(); session.add(OrganizationMember(organization_id=org.id, user_id=user.id, role="owner")); await session.commit(); await session.refresh(org); return org

@router.post("/{organization_id}/members")
async def add_member(organization_id: int, data: MembershipCreate, session: AsyncSession = Depends(get_session), user: UserTable = Depends(fastapi_users.current_user())):
    if data.role not in ROLES: raise HTTPException(422, "Invalid role")
    member = await session.scalar(select(OrganizationMember).where(OrganizationMember.organization_id == organization_id, OrganizationMember.user_id == user.id, OrganizationMember.role.in_(("owner", "admin"))))
    if not member: raise HTTPException(403, "Admin role required")
    if not await session.get(UserTable, data.user_id): raise HTTPException(404, "User not found")
    item = await session.scalar(select(OrganizationMember).where(OrganizationMember.organization_id == organization_id, OrganizationMember.user_id == data.user_id))
    if item: item.role = data.role
    else: item = OrganizationMember(organization_id=organization_id, user_id=data.user_id, role=data.role); session.add(item)
    await session.commit(); await session.refresh(item); return item
