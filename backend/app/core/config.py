from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

import logging

_config_logger = logging.getLogger(__name__)


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
    AI_MAX_RETRIES: int = 2
    AI_RETRY_BASE_DELAY: float = 0.5
    AI_TOTAL_DEADLINE_SECONDS: float = 0.0
    BRAND_EXTRACTION_MODEL: str = "openai/gpt-4.1-mini"
    RUN_TIMEZONE: str = "Asia/Tehran"
    AUTOMATIC_RUN_INTERVAL_SECONDS: int = 60
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_QUEUE_NAME: str = "fanoosai:prompt-runs"
    REDIS_QUEUE_GROUP: str = "fanoosai-workers"
    REDIS_JOB_MAX_RETRIES: int = 3
    WORKER_REQUEST_DELAY_SECONDS: int = 60
    RUN_CLAIM_LEASE_SECONDS: int = 600
    DAILY_MAX_ATTEMPTS: int = 4
    DAILY_RETRY_INTERVAL_MINUTES: int = 15
    DAILY_RETRY_POLL_MINUTES: int = 5
    EXTRACTION_MAX_ATTEMPTS: int = 4
    EXTRACTION_RETRY_BACKOFF_MINUTES: int = 30
    EXTRACTION_RETRY_BATCH_SIZE: int = 5
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


def resolve_ai_total_deadline(s) -> float:
    value = s.AI_TOTAL_DEADLINE_SECONDS
    lease = s.RUN_CLAIM_LEASE_SECONDS
    if value == 0:
        return lease * 0.5
    if value < 10:
        raise ValueError(
            f"AI_TOTAL_DEADLINE_SECONDS must be 0 (auto) or >= 10, got {value}"
        )
    if value >= lease * 0.8:
        _config_logger.warning(
            "AI_TOTAL_DEADLINE_SECONDS=%s risks lease expiry (lease=%s)", value, lease
        )
    return value
