from contextlib import asynccontextmanager
import logging
from fastapi import FastAPI
from fastapi.responses import JSONResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import text

from app.core.config import settings
from app.database.connection import engine
from app.infrastructure.redis_client import close_redis, redis_healthcheck
from app.observability import HTTP_DURATION, HTTP_REQUESTS, configure_logging, duration_seconds, request_id

configure_logging()
logger = logging.getLogger("fanoosai.http")
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

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await close_redis()
    await engine.dispose()

app = FastAPI(title="FanoosAI", lifespan=lifespan)

@app.middleware("http")
async def security_headers(request, call_next):
    start = __import__("time").perf_counter()
    correlation_id = request.headers.get("X-Request-ID") or request_id()
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; base-uri 'self'; frame-ancestors 'none'; object-src 'none'; "
        "script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; "
        "font-src 'self' data:; connect-src 'self' http://localhost:8000 http://127.0.0.1:8000",
    )
    if not settings.DEBUG:
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    route = getattr(request.scope.get("route"), "path", request.url.path)
    status_class = f"{response.status_code // 100}xx"
    HTTP_REQUESTS.labels(request.method, route, status_class).inc()
    HTTP_DURATION.labels(request.method, route).observe(duration_seconds(start))
    response.headers["X-Request-ID"] = correlation_id
    logger.info(
        "http_request_completed",
        extra={
            "request_id": correlation_id,
            "event_data": {
                "method": request.method,
                "route": route,
                "status_code": response.status_code,
                "duration_ms": round(duration_seconds(start) * 1000, 2),
            },
        },
    )
    return response


@app.get("/health/live", include_in_schema=False)
async def liveness() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/ready", include_in_schema=False)
async def readiness() -> dict[str, str]:
    redis_ok = await redis_healthcheck()
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False
    if not redis_ok or not db_ok:
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "database": str(db_ok).lower(), "redis": str(redis_ok).lower()},
        )
    return {"status": "ready", "database": "true", "redis": "true"}


@app.get("/metrics", include_in_schema=False)
async def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


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
