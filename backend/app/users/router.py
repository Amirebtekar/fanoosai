from fastapi import APIRouter
from app.users.schema import UserRead

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserRead)
async def get_current_user():
    """Get current authenticated user - this is handled by FastAPI Users in main.py"""
    pass