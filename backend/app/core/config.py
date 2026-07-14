from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    DATABASE_URL: str = "postgresql+asyncpg://postgres:password@localhost/fanoosai"
    JWT_SECRET_KEY: str = "change-me"
    JWT_LIFETIME_SECONDS: int = 3600
    AI_GATEWAY_BASE_URL: str = "https://my.parspack.com/api/aistudio/api"
    AI_GATEWAY_API_KEY: str = ""

    MELIPAYAMAK_USERNAME: str = ""
    MELIPAYAMAK_PASSWORD: str = ""
    MELIPAYAMAK_FROM_NUMBER: str = ""
    MELIPAYAMAK_SEND_OTP_URL: str = "https://rest.payamak-panel.com/api/SendSMS/SendOtp"

    OTP_TTL: int = 120
    OTP_SEND_COOLDOWN: int = 60
    OTP_MAX_ATTEMPTS: int = 5

settings = Settings()
