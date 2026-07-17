import re
from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, EmailStr, field_validator
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.dependencies import get_session
from app.users.schema import UserRead
from app.services.auth_service import AuthService
from app.auth.jwt import get_jwt_strategy
from app.auth.fastapi_users import fastapi_users
from app.database.models import UserTable

router = APIRouter(prefix="/auth/otp", tags=["otp"])
me_router = APIRouter(prefix="/auth", tags=["auth"])
IR_PHONE_RE = re.compile(r"^09\d{9}$")


class RegisterBody(BaseModel):
    phone: str
    first_name: str
    last_name: str
    email: EmailStr | None = None

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        if not IR_PHONE_RE.match(v):
            raise ValueError("شماره معتبر نیست (مثال: 09123456789)")
        return v


class LoginBody(BaseModel):
    phone: str

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        if not IR_PHONE_RE.match(v):
            raise ValueError("شماره معتبر نیست")
        return v


class VerifyBody(LoginBody):
    code: str

    @field_validator("code")
    @classmethod
    def validate_code(cls, v: str) -> str:
        if not v.isdigit() or len(v) != 6:
            raise ValueError("کد ۶ رقمی وارد کنید")
        return v


class VerifyResponse(BaseModel):
    success: bool = True
    access_token: str | None = None
    token_type: str = "bearer"
    user: UserRead | None = None


def get_auth_service(session: AsyncSession = Depends(get_session)) -> AuthService:
    return AuthService(session)


@me_router.get("/me", response_model=UserRead)
async def get_current_user(user: UserTable = Depends(fastapi_users.current_user())) -> UserTable:
    """Return the authenticated user's safe profile for the dashboard."""
    return user


@router.post("/sms/register")
async def register_sms(body: RegisterBody, service: AuthService = Depends(get_auth_service)):
    await service.register_sms(body.phone, body.first_name, body.last_name, body.email)
    return {"message": "OTP sent", "phone": body.phone}


@router.post("/sms/request")
async def request_sms(body: LoginBody, service: AuthService = Depends(get_auth_service)):
    await service.request_sms(body.phone)
    return {"message": "OTP sent", "phone": body.phone}


@router.post("/sms/verify", response_model=VerifyResponse)
async def verify_sms(body: VerifyBody, response: Response, service: AuthService = Depends(get_auth_service)):
    user = await service.verify_sms(body.phone, body.code)
    token = await get_jwt_strategy().write_token(user)
    response.set_cookie(
        key="access_token",
        value=token,
        max_age=settings.JWT_LIFETIME_SECONDS,
        httponly=True,
        secure=not settings.DEBUG,
        samesite="lax",
        path="/",
    )
    if settings.DEBUG:
        return {"success": True, "token_type": "bearer", "user": user}
    return {"success": True, "token_type": "bearer"}
