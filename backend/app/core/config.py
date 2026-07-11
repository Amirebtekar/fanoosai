from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    DATABASE_URL: str = "postgresql+asyncpg://postgres:password@localhost/fanoosai"
    JWT_SECRET_KEY: str = "change-me"
    JWT_LIFETIME_SECONDS: int = 3600

    MELIPAYAMAK_BASE_URL: str = "https://api.parspack.com/api/aistudio/api/v1"
    MELIPAYAMAK_USERNAME: str = ""
    MELIPAYAMAK_PASSWORD: str = ""
    MELIPAYAMAK_FROM_NUMBER: str = ""


settings = Settings()
