import jwt
from datetime import datetime, timedelta
from fastapi import Depends
from fastapi_users.authentication import JWTStrategy
from app.core.config import settings


def get_jwt_strategy() -> JWTStrategy:
    return JWTStrategy(
        secret=settings.JWT_SECRET_KEY,
        lifetime_seconds=settings.JWT_LIFETIME_SECONDS,
    )