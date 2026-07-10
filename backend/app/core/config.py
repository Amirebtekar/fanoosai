from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:password@localhost/fanoosai"
    DB_ECHO: bool = False

    # JWT
    JWT_SECRET_KEY: str = "your-super-secret-jwt-key-change-me"
    SECRET_KEY: str = "your-super-secret-jwt-key-change-me"
    JWT_LIFETIME_SECONDS: int = 3600

    # Melipayamak SMS
    MELIPAYAMAK_BASE_URL: str = "https://api.parspack.com/api/aistudio/api/v1"
    MELIPAYAMAK_USERNAME: str = ""
    MELIPAYAMAK_PASSWORD: str = ""
    MELIPAYAMAK_FROM_NUMBER: str = ""
    MELIPAYAMAK_SENDER: str = ""

    # App
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000


settings = Settings()
