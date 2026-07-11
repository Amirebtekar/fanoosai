from typing import Optional
from pydantic import EmailStr, Field
from fastapi_users import schemas


class UserRead(schemas.BaseUser[int]):
    phone: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None


class UserCreate(schemas.BaseUserCreate):
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, min_length=10, max_length=20)


class UserUpdate(schemas.BaseUserUpdate):
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, min_length=10, max_length=20)
