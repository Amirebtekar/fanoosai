from fastapi_users import FastAPIUsers
from fastapi_users.authentication import AuthenticationBackend, BearerTransport

from app.database.models import UserTable
from app.users.manager import get_user_manager
from app.auth.jwt import get_jwt_strategy


jwt_backend = AuthenticationBackend(
    name="jwt",
    transport=BearerTransport(tokenUrl="auth/jwt/login"),
    get_strategy=get_jwt_strategy,
)

fastapi_users = FastAPIUsers[UserTable, int](get_user_manager, [jwt_backend])