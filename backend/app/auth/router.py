from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.auth.sms_service import melipayamak_client
from app.auth.jwt import get_jwt_strategy
from app.users.service import get_user_service, UserService
from app.core.config import settings
import random
import time

router = APIRouter(prefix="/auth/otp", tags=["otp"])

# Simple in-memory OTP store: {phone: {"code": str, "expires_at": float}}
otp_store: dict[str, dict] = {}

OTP_EXPIRY_SECONDS = 120  # 2 minutes


class OTPRequest(BaseModel):
    phone: str


class OTPVerify(BaseModel):
    phone: str
    code: str


def _generate_otp() -> str:
    return str(random.randint(100000, 999999))


def _store_otp(phone: str, code: str) -> None:
    otp_store[phone] = {
        "code": code,
        "expires_at": time.time() + OTP_EXPIRY_SECONDS,
    }


def _verify_stored_otp(phone: str, code: str) -> bool:
    stored = otp_store.pop(phone, None)
    if stored is None:
        return False
    if time.time() > stored["expires_at"]:
        return False
    return stored["code"] == code


@router.post("/sms/request")
async def request_sms_otp(
    body: OTPRequest,
    user_service: UserService = Depends(get_user_service),
):
    """Send OTP code to phone number via SMS"""
    user = await user_service.get_by_phone(body.phone)
    if not user:
        raise HTTPException(status_code=404, detail="User not found with this phone number")

    otp_code = _generate_otp()
    _store_otp(body.phone, otp_code)

    success = await melipayamak_client.send_otp(body.phone, otp_code)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to send OTP")

    return {"message": "OTP sent successfully", "phone": body.phone}


@router.post("/sms/verify")
async def verify_sms_otp(
    body: OTPVerify,
    user_service: UserService = Depends(get_user_service),
):
    """Verify OTP code and return JWT token"""
    if not _verify_stored_otp(body.phone, body.code):
        raise HTTPException(status_code=400, detail="Invalid or expired OTP code")

    user = await user_service.get_by_phone(body.phone)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    strategy = get_jwt_strategy()
    token = await strategy.write_token(user)

    return {"access_token": token, "token_type": "bearer"}


@router.post("/email/request")
async def request_email_otp(
    body: OTPRequest,
    user_service: UserService = Depends(get_user_service),
):
    """Send OTP code to user's email"""
    user = await user_service.get_by_phone(body.phone)
    if not user or not user.email:
        raise HTTPException(status_code=404, detail="User not found or no email set")

    otp_code = _generate_otp()
    _store_otp(body.phone, otp_code)

    # TODO: Implement email sending (e.g., via SMTP or SendGrid)
    print(f"[DEV] Email OTP for {user.email}: {otp_code}")

    return {"message": "OTP sent to email", "phone": body.phone}
