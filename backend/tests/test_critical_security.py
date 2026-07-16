import pytest
from pydantic import ValidationError

from app.auth.router import RegisterBody, register_sms
from app.core.config import Settings


def test_settings_require_database_url_and_jwt_secret(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("JWT_SECRET_KEY", raising=False)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


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
