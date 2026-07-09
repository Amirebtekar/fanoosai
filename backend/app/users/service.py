from typing import Optional
from fastapi import Depends
from fastapi_users.db import SQLAlchemyUserDatabase

from app.database.models import UserTable
from app.users.schema import UserCreate, UserRead


class UserService:
    def __init__(self, user_db: SQLAlchemyUserDatabase = Depends(get_user_db)):
        self.user_db = user_db

    async def get_by_email(self, email: str) -> Optional[UserRead]:
        user = await self.user_db.get_by_email(email)
        return user

    async def get_by_phone(self, phone: str) -> Optional[UserRead]:
        user = await self.user_db.get_by_field("phone", phone)
        return user

    async def create_user(self, user_create: UserCreate) -> UserRead:
        user = await self.user_db.create(user_create)
        return user


def get_user_service(user_db: SQLAlchemyUserDatabase = Depends(get_user_db)):
    return UserService(user_db)