from typing import Optional
from fastapi import Depends, Request
from fastapi_users import BaseUserManager, IntegerIDMixin
from app.database.models import UserTable
from app.core.config import settings


class UserManager(IntegerIDMixin, BaseUserManager[UserTable, int]):
    reset_password_token_secret = settings.JWT_SECRET_KEY
    verification_token_secret = settings.JWT_SECRET_KEY

    async def on_after_register(self, user: UserTable, request: Optional[Request] = None):
        print(f"User {user.id} registered.")

    async def on_after_forgot_password(self, user: UserTable, token: str, request: Optional[Request] = None):
        print(f"User {user.id} forgot password. Token: {token}")

    async def on_after_request_verify(self, user: UserTable, token: str, request: Optional[Request] = None):
        print(f"Verification requested for user {user.id}. Token: {token}")


async def get_user_manager(user_db=Depends(__import__("app.database.models", fromlist=["get_user_db"]).get_user_db)):
    yield UserManager(user_db)
