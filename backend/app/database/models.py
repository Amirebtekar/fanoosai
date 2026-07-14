from typing import AsyncGenerator
from datetime import datetime
from sqlalchemy import String, Boolean, Integer, ForeignKey, DateTime, UniqueConstraint, func, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from fastapi_users.db import SQLAlchemyBaseUserTable, SQLAlchemyUserDatabase
from app.database.connection import Base, async_session_maker


class AIModel(Base):
    __tablename__ = "ai_models"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    model_key: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    prompts: Mapped[list["PromptModel"]] = relationship("PromptModel", back_populates="model")


class PromptModel(Base):
    __table_args__ = (UniqueConstraint("prompt_id", "ai_model_id", name="uq_prompt_model"),)
    __tablename__ = "prompt_models"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    prompt_id: Mapped[int] = mapped_column(Integer, ForeignKey("prompts.id"), nullable=False)
    ai_model_id: Mapped[int] = mapped_column(Integer, ForeignKey("ai_models.id"), nullable=False)
    
    prompt: Mapped["Prompt"] = relationship("Prompt", back_populates="models")
    model: Mapped["AIModel"] = relationship("AIModel", back_populates="prompts")


class UserTable(Base, SQLAlchemyBaseUserTable):
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str | None] = mapped_column(String(320), unique=True, nullable=True)
    phone: Mapped[str | None] = mapped_column(String(20), unique=True, nullable=True)
    first_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    hashed_password: Mapped[str] = mapped_column(String(1024))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    
    # Relationship to projects
    projects: Mapped[list["Project"]] = relationship("Project", back_populates="user", lazy="selectin")


class Project(Base):
    __tablename__ = "projects"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    website_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey(UserTable.id), nullable=False)
    
    # Relationship to user
    user: Mapped[UserTable] = relationship("UserTable", back_populates="projects")
    prompts: Mapped[list["Prompt"]] = relationship("Prompt", back_populates="project", lazy="selectin")


class Prompt(Base):
    __tablename__ = "prompts"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(Integer, ForeignKey("projects.id"), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
        # Relationship to project
    project: Mapped[Project] = relationship("Project", back_populates="prompts")
    models: Mapped[list["PromptModel"]] = relationship("PromptModel", back_populates="prompt")

async def get_user_db() -> AsyncGenerator[SQLAlchemyUserDatabase, None]:
    async with async_session_maker() as session:
        yield SQLAlchemyUserDatabase(session, UserTable)
