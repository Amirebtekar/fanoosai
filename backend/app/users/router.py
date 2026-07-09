from fastapi import APIRouter, Depends
from fastapi_users import FastAPIUsers
from fastapi_users.authentication import JWTStrategy, AccessTokenBackend

from app.database.models import UserTable, get_user_db
from app.users.schema import UserRead, UserCreate, UserUpdate
from app.auth.jwt import get_jwt_strategy, get_access_token_backend

router = APIRouter()


def get_fastapi_users():
    from fastapi_users import FastAPIUsers
    from app.database.connection import async_session_maker

    async def get_user_db():
        async with async_session_maker() as session:
            yield SQLAlchemyUserDatabase(session, UserTable)

    fastapi_users = FastAPIUsers[UserTable, int](
        get_user_db,
        [get_jwt_strategy()],
    )
    return fastapi_users


@router.get("/users/me", response_model=UserRead)
async def get_current_user(
    fastapi_users: FastAPIUsers = Depends(get_fastapi_users),
    user: UserRead = Depends(fastapi_users.current_user()),
):
    return user