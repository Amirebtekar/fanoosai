from fastapi_users.db import SQLAlchemyBaseUserTable, SQLAlchemyUserDatabase
from sqlalchemy import String, Boolean, Column, Integer
from sqlalchemy.orm import Mapped, mapped_column
from app.database.connection import Base


class UserTable(Base, SQLAlchemyBaseUserTable):
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(length=320), unique=True,    nullable=True)
    phone: Mapped[str] = mapped_column(String(length=20), unique=True, nullable=True)
    hashed_password: Mapped[str] = mapped_column(String(length=1024))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


async def get_user_db(session: AsyncSession):
    yield SQLAlchemyUserDatabase(session, UserTable)