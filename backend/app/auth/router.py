import random
import time
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from app.auth.sms_service import sms_client
from app.auth.jwt import get_jwt_strategy
from app.auth.password import get_password_hash
from app.database.models import UserTable, async_session_maker

router = APIRouter(prefix="/auth/otp", tags=["otp"])

# In-memory OTP store: {phone: {"code": str, "expires_at": float}}
otp_store: dict[str, dict] = {}
OTP_TTL = 120  # seconds


class PhoneBody(BaseModel):
    phone: str


class VerifyBody(BaseModel):
    phone: str
    code: str


def _generate() -> str:
    return str(random.randint(100000, 999999))


def _store(phone: str, code: str):
    otp_store[phone] = {"code": code, "expires_at": time.time() + OTP_TTL}


def _check(phone: str, code: str) -> bool:
    stored = otp_store.pop(phone, None)
    if not stored:
        return False
    if time.time() > stored["expires_at"]:
        return False
    return stored["code"] == code


@router.post("/sms/register")
async def register_sms(body: PhoneBody):
    """Register user by phone (or find existing) and send OTP."""
    async with async_session_maker() as session:
        stmt = select(UserTable).where(UserTable.phone == body.phone)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            user = UserTable(
                phone=body.phone,
                email=None,
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
async def request_sms(body: PhoneBody):
    """Send OTP to existing user."""
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
    if not _check(body.phone, body.code):
        raise HTTPException(400, "Invalid or expired code")

    async with async_session_maker() as session:
        stmt = select(UserTable).where(UserTable.phone == body.phone)
        user = (await session.execute(stmt)).scalar_one_or_none()

    if not user:
        raise HTTPException(404, "User not found")

    token = await get_jwt_strategy().write_token(user)
    return {"access_token": token, "token_type": "bearer"}
