from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi_users import FastAPIUsers
from fastapi_users.authentication import JWTStrategy

from app.database.connection import create_db_and_tables
from app.database.models import UserTable, get_user_db
from app.users.schema import UserRead, UserCreate, UserUpdate
from app.auth.jwt import get_jwt_strategy

app = FastAPI(title="FanoosAI API")

origins = [
    "http://localhost:3000",
    "http://localhost:8000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_fastapi_users():
    fastapi_users = FastAPIUsers[UserTable, int](
        get_user_db,
        [get_jwt_strategy()],
    )
    return fastapi_users


@app.on_event("startup")
async def startup():
    await create_db_and_tables()


@app.get("/")
async def root():
    return {"message": "FanoosAI API is running"}