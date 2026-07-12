from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.models import UserTable


class UserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_phone(self, phone: str) -> UserTable | None:
        stmt = select(UserTable).where(UserTable.phone == phone)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, **kwargs) -> UserTable:
        user = UserTable(**kwargs)
        self.session.add(user)
        await self.session.commit()
        return user

    async def mark_verified(self, user: UserTable) -> None:
        user.is_verified = True
        await self.session.commit()
