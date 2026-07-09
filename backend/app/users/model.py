from typing import Optional
from pydantic import EmailStr, Field
from fastapi_users import schemas


class UserRead(schemas.BaseUser[int]):
    phone: Optional[str] = None


class UserCreate(schemas.BaseUserCreate):
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, min_length=10, max_length=20)
    password: str

    # At least one of email or phone must be provided
    @classmethod
    def validate_identity(cls, values):
        if not values.get("email") and not values.get("phone"):
            raise ValueError("Either email or phone must be provided")
        return values