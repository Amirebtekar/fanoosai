import random
import re
import time
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, field_validator
from sqlalchemy import select
from app.auth.sms_service import sms_client
from app.auth.jwt import get_jwt_strategy
from app.auth.password import get_password_hash
from app.core.config import settings
from app.database.models import UserTable, async_session_maker

router = APIRouter(prefix="/auth/otp", tags=["otp"])

# In-memory stores
otp_store: dict[str, dict] = {}
rate_limit: dict[str, float] = {}       # {phone: last_send_time}
attempt_store: dict[str, int] = {}      # {phone: attempts}

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


class VerifyBody(BaseModel):
    phone: str
    code: str

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        if not IR_PHONE_RE.match(v):
            raise ValueError("شماره معتبر نیست")
        return v

    @field_validator("code")
    @classmethod
    def validate_code(cls, v: str) -> str:
        if not v.isdigit() or len(v) != 6:
            raise ValueError("کد ۶ رقمی وارد کنید")
        return v


def _generate() -> str:
    return str(random.randint(100000, 999999))


def _check_send_rate(phone: str) -> None:
    now = time.time()
    last = rate_limit.get(phone, 0)
    if now - last < settings.OTP_SEND_COOLDOWN:
        remaining = int(settings.OTP_SEND_COOLDOWN - (now - last))
        raise HTTPException(429, f"لطفاً {remaining} ثانیه صبر کنید")


def _check_attempts(phone: str) -> None:
    if attempt_store.get(phone, 0) >= settings.OTP_MAX_ATTEMPTS:
        attempt_store.pop(phone, None)
        otp_store.pop(phone, None)
        raise HTTPException(429, "تعداد تلاش‌ها زیاد بود. مجدداً کد بگیرید")


def _store(phone: str, code: str):
    otp_store[phone] = {"code": code, "expires_at": time.time() + settings.OTP_TTL}
    rate_limit[phone] = time.time()
    attempt_store.pop(phone, None)  # reset attempts on new code


def _check(phone: str, code: str) -> bool:
    stored = otp_store.get(phone)
    if not stored:
        return False
    if time.time() > stored["expires_at"]:
        otp_store.pop(phone, None)
        return False
    if stored["code"] != code:
        attempt_store[phone] = attempt_store.get(phone, 0) + 1
        return False
    # correct — clean up
    otp_store.pop(phone, None)
    attempt_store.pop(phone, None)
    return True


@router.post("/sms/register")
async def register_sms(body: RegisterBody):
    """Register user by phone (or find existing) and send OTP."""
    _check_send_rate(body.phone)

    async with async_session_maker() as session:
        stmt = select(UserTable).where(UserTable.phone == body.phone)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            user = UserTable(
                phone=body.phone,
                email=body.email,
                first_name=body.first_name,
                last_name=body.last_name,
                hashed_password=get_password_hash("sms-only"),
                is_active=True,
            )
            session.add(user)
            await session.commit()

    code = _generate()
    _store(body.phone, code)

    # ponytail: in dev, return code in response. remove when real SMS works.
    sent = await sms_client.send_otp(body.phone, code)
    if not sent:
        print(f"[DEV] OTP for {body.phone}: {code}")

    return {"message": "OTP sent", "phone": body.phone, "_dev_code": code if not sent else None}


@router.post("/sms/request")
async def request_sms(body: LoginBody):
    """Send OTP to existing user."""
    _check_send_rate(body.phone)

    async with async_session_maker() as session:
        stmt = select(UserTable).where(UserTable.phone == body.phone)
        user = (await session.execute(stmt)).scalar_one_or_none()

        if not user:
            raise HTTPException(400, "User not found. Register first.")

    code = _generate()
    _store(body.phone, code)

    sent = await sms_client.send_otp(body.phone, code)
    if not sent:
        print(f"[DEV] OTP for {body.phone}: {code}")

    return {"message": "OTP sent", "phone": body.phone, "_dev_code": code if not sent else None}


@router.post("/sms/verify")
async def verify_sms(body: VerifyBody):
    """Verify OTP → return JWT."""
    _check_attempts(body.phone)

    if not _check(body.phone, body.code):
        remaining = settings.OTP_MAX_ATTEMPTS - attempt_store.get(body.phone, 0)
        if remaining <= 0:
            raise HTTPException(429, "تعداد تلاش‌ها تمام شد. مجدداً کد بگیرید")
        raise HTTPException(400, f"کد اشتباه است. {remaining} تلاش باقی‌مانده")

    async with async_session_maker() as session:
        stmt = select(UserTable).where(UserTable.phone == body.phone)
        user = (await session.execute(stmt)).scalar_one_or_none()

        if not user:
            raise HTTPException(404, "User not found")

        user.is_verified = True
        await session.commit()

    token = await get_jwt_strategy().write_token(user)
    return {"access_token": token, "token_type": "bearer"}
