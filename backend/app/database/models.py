from typing import AsyncGenerator
from sqlalchemy import String, Boolean, Integer
from sqlalchemy.orm import Mapped, mapped_column
from fastapi_users.db import SQLAlchemyBaseUserTable, SQLAlchemyUserDatabase
from app.database.connection import Base, async_session_maker


class UserTable(Base, SQLAlchemyBaseUserTable):
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str | None] = mapped_column(String(320), unique=True, nullable=True)
    phone: Mapped[str | None] = mapped_column(String(20), unique=True, nullable=True)
    hashed_password: Mapped[str] = mapped_column(String(1024))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


async def get_user_db() -> AsyncGenerator[SQLAlchemyUserDatabase, None]:
    async with async_session_maker() as session:
        yield SQLAlchemyUserDatabase(session, UserTable)
