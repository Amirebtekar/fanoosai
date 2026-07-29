import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.auth.router import RegisterBody, register_sms
from app.core.config import Settings
from app.core.config import settings
from app.services.auth_service import AuthService, OTPStore


def test_settings_require_database_url_and_jwt_secret(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("JWT_SECRET_KEY", raising=False)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_release_debug_value_is_treated_as_production():
    configured = Settings(
        DEBUG="release",
        DATABASE_URL="postgresql+asyncpg://localhost/test",
        JWT_SECRET_KEY="x" * 32,
        _env_file=None,
    )

    assert configured.DEBUG is False


@pytest.mark.asyncio
async def test_register_sms_never_returns_otp_in_response():
    class ServiceStub:
        async def register_sms(self, phone, first_name, last_name, email):
            return "123456"

    response = await register_sms(
        RegisterBody(
            phone="09123456789",
            first_name="Test",
            last_name="User",
            email=None,
        ),
        ServiceStub(),
    )

    assert "_dev_code" not in response
    assert response == {"message": "OTP sent", "phone": "09123456789"}


@pytest.mark.asyncio
async def test_fixed_otp_is_available_only_for_configured_debug_phone(monkeypatch):
    class UserRepositoryStub:
        async def get_by_phone(self, phone):
            return object()

    monkeypatch.setattr(settings, "DEBUG", True)
    monkeypatch.setattr(settings, "DEV_OTP_PHONE", "09101418818")
    monkeypatch.setattr(settings, "DEV_OTP_CODE", "123456")

    service = AuthService.__new__(AuthService)
    service.user_repo = UserRepositoryStub()
    service.otp_store = OTPStore()

    await service.request_sms("09101418818")

    assert await service.otp_store.verify("09101418818", "123456") == -1


def test_fixed_otp_is_disabled_when_debug_is_false(monkeypatch):
    monkeypatch.setattr(settings, "DEBUG", False)
    monkeypatch.setattr(settings, "DEV_OTP_PHONE", "09101418818")
    monkeypatch.setattr(settings, "DEV_OTP_CODE", "123456")

    assert not AuthService._is_dev_otp("09101418818")


@pytest.mark.asyncio
async def test_verify_sms_uses_atomic_attempt_result(monkeypatch):
    class StoreStub:
        async def verify(self, phone, code):
            return settings.OTP_MAX_ATTEMPTS

    service = AuthService.__new__(AuthService)
    service.otp_store = StoreStub()
    service.user_repo = object()

    with pytest.raises(HTTPException) as exc:
        await service.verify_sms("09123456789", "000000")

    assert exc.value.status_code == 429
