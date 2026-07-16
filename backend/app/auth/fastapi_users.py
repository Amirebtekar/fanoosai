from fastapi_users import FastAPIUsers
from fastapi_users.authentication import AuthenticationBackend, CookieTransport

from app.database.models import UserTable
from app.users.manager import get_user_manager
from app.auth.jwt import get_jwt_strategy
from app.core.config import settings


jwt_backend = AuthenticationBackend(
    name="jwt",
    transport=CookieTransport(
        cookie_name="access_token",
        cookie_max_age=settings.JWT_LIFETIME_SECONDS,
        cookie_secure=not settings.DEBUG,
        cookie_httponly=True,
        cookie_samesite="lax",
    ),
    get_strategy=get_jwt_strategy,
)

fastapi_users = FastAPIUsers[UserTable, int](get_user_manager, [jwt_backend])
