from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi_users.authentication import AuthenticationBackend, BearerTransport

from app.core.config import settings
from app.database.connection import create_db_and_tables
from app.database.models import UserTable, get_user_db
from app.users.schema import UserRead, UserCreate, UserUpdate
from app.users.manager import get_user_manager
from app.auth.jwt import get_jwt_strategy
from app.auth.router import router as otp_router
from app.auth.fastapi_users import fastapi_users, jwt_backend
from app.projects.router import router as projects_router
from app.projects.prompt_router import router as prompts_router
from app.projects.ai_models_router import router as ai_models_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    await create_db_and_tables()
    yield

app = FastAPI(title="FanoosAI", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(fastapi_users.get_auth_router(jwt_backend), prefix="/auth/jwt", tags=["auth"])
app.include_router(fastapi_users.get_register_router(UserRead, UserCreate), prefix="/auth", tags=["auth"])
app.include_router(fastapi_users.get_verify_router(UserRead), prefix="/auth", tags=["auth"])
app.include_router(fastapi_users.get_users_router(UserRead, UserUpdate), prefix="/users", tags=["users"])
app.include_router(otp_router)
app.include_router(projects_router)
app.include_router(prompts_router)
app.include_router(ai_models_router)

@app.get("/")
async def root():
    return {"message": "FanoosAI API is running"}
