from contextlib import asynccontextmanager
import asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi_users.authentication import AuthenticationBackend, BearerTransport

from app.core.config import settings
from app.database.connection import create_db_and_tables
from app.database.models import UserTable, get_user_db
from app.users.schema import UserRead, UserCreate, UserUpdate
from app.users.manager import get_user_manager
from app.auth.jwt import get_jwt_strategy
from app.auth.router import router as otp_router, me_router
from app.auth.fastapi_users import fastapi_users, jwt_backend
from app.projects.router import router as projects_router
from app.projects.prompt_router import router as prompts_router
from app.projects.ai_models_router import router as ai_models_router
from app.analytics.router import router as analytics_router
from app.analytics.extra_router import router as analytics_extra_router
from app.services.automatic_run_service import automatic_run_loop

@asynccontextmanager
async def lifespan(app: FastAPI):
    await create_db_and_tables()
    automatic_task = asyncio.create_task(automatic_run_loop())
    try:
        yield
    finally:
        automatic_task.cancel()
        await asyncio.gather(automatic_task, return_exceptions=True)

app = FastAPI(title="FanoosAI", lifespan=lifespan)

@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    if not settings.DEBUG:
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return response


def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(title=app.title, version="1.0.0", routes=app.routes)
    app.openapi_schema = schema
    return schema


app.openapi = custom_openapi

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.CORS_ORIGINS.split(",") if origin.strip()],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-CSRF-Token"],
)

app.include_router(fastapi_users.get_auth_router(jwt_backend), prefix="/auth/jwt", tags=["auth"])
app.include_router(fastapi_users.get_register_router(UserRead, UserCreate), prefix="/auth", tags=["auth"])
app.include_router(fastapi_users.get_verify_router(UserRead), prefix="/auth", tags=["auth"])
app.include_router(fastapi_users.get_users_router(UserRead, UserUpdate), prefix="/users", tags=["users"])
app.include_router(otp_router)
app.include_router(me_router)
app.include_router(projects_router)
app.include_router(prompts_router)
app.include_router(ai_models_router)
app.include_router(analytics_router)
app.include_router(analytics_extra_router)

@app.get("/")
async def root():
    return {"message": "FanoosAI API is running"}
