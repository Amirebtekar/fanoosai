from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[2] / ".env",
        env_file_encoding="utf-8",
    )

    DEBUG: bool = False
    DATABASE_URL: str
    JWT_SECRET_KEY: str
    JWT_LIFETIME_SECONDS: int = 36000
    CORS_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173,http://127.0.0.1:5173,http://localhost:5174,http://127.0.0.1:5174"
    AI_GATEWAY_BASE_URL: str = "https://my.parspack.com/api/aistudio/api"
    AI_GATEWAY_API_KEY: str = ""
    AI_GATEWAY_ENABLED: bool = False
    AVALAI_BASE_URL: str = "https://api.avalai.ir/v1"
    AVALAI_API_KEY: str = ""
    AVALAI_MODEL: str = ""
    BRAND_EXTRACTION_MODEL: str = "openai/gpt-4.1-mini"
    RUN_TIMEZONE: str = "Asia/Tehran"
    AUTOMATIC_RUN_INTERVAL_SECONDS: int = 60
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_QUEUE_NAME: str = "fanoosai:prompt-runs"
    REDIS_QUEUE_GROUP: str = "fanoosai-workers"
    REDIS_JOB_MAX_RETRIES: int = 3
    RUN_CLAIM_LEASE_SECONDS: int = 600
    RUN_RETENTION_DAYS: int = 365
    TREND_MAX_POINTS_PER_SERIES: int = 365
    ANALYTICS_PROMPT_LIMIT: int = 1000
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_TIMEOUT_SECONDS: int = 10
    DB_POOL_RECYCLE_SECONDS: int = 1800

    INTERNAL_API_KEY: str = ""

    MELIPAYAMAK_USERNAME: str = ""
    MELIPAYAMAK_PASSWORD: str = ""
    MELIPAYAMAK_FROM_NUMBER: str = ""
    MELIPAYAMAK_SEND_OTP_URL: str = "https://rest.payamak-panel.com/api/SendSMS/SendOtp"

    OTP_TTL: int = 120
    OTP_SEND_COOLDOWN: int = 60
    OTP_MAX_ATTEMPTS: int = 5

    # Development-only OTP. It is usable only when DEBUG is enabled and the
    # requested phone exactly matches DEV_OTP_PHONE.
    DEV_OTP_PHONE: str = ""
    DEV_OTP_CODE: str = ""

    @field_validator("DEBUG", mode="before")
    @classmethod
    def normalize_debug(cls, value):
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"release", "production", "prod"}:
                return False
            if normalized in {"development", "dev"}:
                return True
        return value

    @field_validator("JWT_SECRET_KEY")
    @classmethod
    def validate_jwt_secret(cls, value: str) -> str:
        if len(value) < 32 or value in {"change-me", "your-secret-key-here"}:
            raise ValueError("JWT_SECRET_KEY must be a non-default secret of at least 32 characters")
        return value


settings = Settings()
