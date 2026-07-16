from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    DEBUG: bool = False
    DATABASE_URL: str
    JWT_SECRET_KEY: str
    JWT_LIFETIME_SECONDS: int = 36000
    AI_GATEWAY_BASE_URL: str = "https://my.parspack.com/api/aistudio/api"
    AI_GATEWAY_API_KEY: str = ""
    BRAND_EXTRACTION_MODEL: str = "openai/gpt-4.1-mini"

    MELIPAYAMAK_USERNAME: str = ""
    MELIPAYAMAK_PASSWORD: str = ""
    MELIPAYAMAK_FROM_NUMBER: str = ""
    MELIPAYAMAK_SEND_OTP_URL: str = "https://rest.payamak-panel.com/api/SendSMS/SendOtp"

    OTP_TTL: int = 120
    OTP_SEND_COOLDOWN: int = 60
    OTP_MAX_ATTEMPTS: int = 5

    @field_validator("JWT_SECRET_KEY")
    @classmethod
    def validate_jwt_secret(cls, value: str) -> str:
        if len(value) < 32 or value in {"change-me", "your-secret-key-here"}:
            raise ValueError("JWT_SECRET_KEY must be a non-default secret of at least 32 characters")
        return value


settings = Settings()
