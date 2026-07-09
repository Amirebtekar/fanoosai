from typing import Optional
from pydantic import BaseModel, EmailStr, Field
from fastapi_users import schemas


class UserRead(schemas.BaseUser[int]):
    phone: Optional[str] = None


class UserCreate(schemas.BaseUserCreate):
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, min_length=10, max_length=20)


class UserUpdate(schemas.BaseUserUpdate):
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, min_length=10, max_length=20)
    password: Optional[str] = None


class UserDB(schemas.BaseUserDB[int]):
    phone: Optional[str] = None