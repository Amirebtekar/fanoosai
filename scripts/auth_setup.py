#!/usr/bin/env python3
"""FanoosAI Authentication - FastAPI Users with Email + SMS OTP"""

import os
from typing import Optional, Dict, Any

from fastapi import FastAPI, Depends, Request, HTTPException
from fastapi_users import FastAPIUsers, BaseUserManager, IntegerIDMixin
from fastapi_users.authentication import (
    AuthenticationBackend,
    BearerTransport,
    JWTStrategy,
)
from fastapi_users.db import SQLAlchemyUserDatabase
from fastapi_users.jwt import generate_jwt
from fastapi_users.models import BaseUserDB
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.ext.declarative import DeclarativeMeta, declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy import Column, Integer, String, Boolean
from dotenv import load_dotenv
import secrets
import asyncio

# Load environment variables
load_dotenv()

# Configuration
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:password@localhost:5432/fanoosai")
SECRET_KEY = os.getenv("SECRET_KEY", secrets.token_urlsafe(32))

# Melipayamak configuration
MELIPAYAMAK_USERNAME = os.getenv("MELIPAYAMAK_USERNAME")
MELIPAYAMAK_PASSWORD = os.getenv("MELIPAYAMAK_PASSWORD")
MELIPAYAMAK_SENDER = os.getenv("MELIPAYAMAK_SENDER")

engine = create_async_engine(DATABASE_URL)
async_session_maker = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
Base: DeclarativeMeta = declarative_base()


# User model
class User(BaseUserDB, IntegerIDMixin):
    phone_number = Column(String, nullable=True)
    email_verified = Column(Boolean, default=False)


# User database adapter
async def get_user_db(session: AsyncSession = Depends(async_session_maker)):
    yield SQLAlchemyUserDatabase(session, User)


# User manager
class UserManager(IntegerIDMixin, BaseUserManager[User, int]):
    reset_password_token_secret = SECRET_KEY
    verification_token_secret = SECRET_KEY
    
    async def on_after_register(self, user: User, request: Optional[Request] = None):
        print(f"User {user.id} has registered.")
        
    async def on_after_forgot_password(self, user: User, token: str, request: Optional[Request] = None):
        print(f"User {user.id} has forgot their password. Token: {token}")
        
    async def on_after_request_verify(self, user: User, token: str, request: Optional[Request] = None):
        print(f"Verification requested for user {user.id}. Token: {token}")


async def get_user_manager(user_db=Depends(get_user_db)):
    yield UserManager(user_db)


# Authentication
bearer_transport = BearerTransport(tokenUrl="auth/jwt/login")

def get_jwt_strategy() -> JWTStrategy:
    return JWTStrategy(secret=SECRET_KEY, lifetime_seconds=3600)


auth_backend = AuthenticationBackend(
    name="jwt",
    transport=bearer_transport,
    get_strategy=get_jwt_strategy,
)


# FastAPI app
app = FastAPI(title="FanoosAI Authentication")

fastapi_users = FastAPIUsers[User, int](
    get_user_manager,
    [auth_backend],
)

app.include_router(
    fastapi_users.get_auth_router(auth_backend),
    prefix="/auth/jwt",
    tags=["auth"],
)
app.include_router(
    fastapi_users.get_register_router(),
    prefix="/auth",
    tags=["auth"],
)
app.include_router(
    fastapi_users.get_users_router(),
    prefix="/users",
    tags=["users"],
)


# OTP Manager - handles both email and SMS OTP
class OTPManager:
    def __init__(self):
        self.email_otps: Dict[str, Dict[str, Any]] = {}
        self.sms_otps: Dict[str, Dict[str, Any]] = {}
        self.email_sessions: Dict[str, Dict[str, Any]] = {}
        self.sms_sessions: Dict[str, Dict[str, Any]] = {}
    
    async def send_email_otp(self, email: str) -> str:
        """Send OTP to email and return session ID"""
        code = secrets.randbelow(900000) + 100000
        session_id = secrets.token_urlsafe(32)
        
        self.email_otps[email] = {
            "code": str(code),
            "attempts": 0,
            "created_at": asyncio.get_event_loop().time()
        }
        self.email_sessions[session_id] = {"email": email}
        
        # TODO: Replace with actual email sending
        print(f"[EMAIL OTP] Code for {email}: {code}")
        
        return session_id
    
    async def send_sms_otp(self, phone_number: str) -> str:
        """Send OTP via Melipayamak and return session ID"""
        code = secrets.randbelow(900000) + 100000
        session_id = secrets.token_urlsafe(32)
        
        self.sms_otps[phone_number] = {
            "code": str(code),
            "attempts": 0,
            "created_at": asyncio.get_event_loop().time()
        }
        self.sms_sessions[session_id] = {"phone_number": phone_number}
        
        # Send via Melipayamak
        await self._send_via_melipayamak(phone_number, code)
        
        return session_id
    
    async def _send_via_melipayamak(self, phone_number: str, code: int) -> bool:
        """Send SMS using Melipayamak API"""
        try:
            import requests
            
            if not all([MELIPAYAMAK_USERNAME, MELIPAYAMAK_PASSWORD, MELIPAYAMAK_SENDER]):
                print("[SMS] Melipayamak credentials not configured")
                return False
            
            url = "http://api.payamak-panel.com/post/Send.asmx/SendOtp"
            payload = {
                "username": MELIPAYAMAK_USERNAME,
                "password": MELIPAYAMAK_PASSWORD,
                "from": MELIPAYAMAK_SENDER,
                "to": phone_number,
                "code": code,
            }
            
            response = requests.post(url, json=payload, timeout=30)
            result = response.text
            
            print(f"[SMS] Melipayamak response: {result}")
            return "recId" in result or result.isdigit()
        except Exception as e:
            print(f"[SMS] Failed to send: {e}")
            return False
    
    async def verify_email_otp(self, session_id: str, code: str) -> bool:
        """Verify email OTP code"""
        if session_id not in self.email_sessions:
            return False
            
        email = self.email_sessions[session_id]["email"]
        
        if email not in self.email_otps:
            return False
            
        if self.email_otps[email]["code"] != code:
            self.email_otps[email]["attempts"] += 1
            if self.email_otps[email]["attempts"] >= 5:
                del self.email_otps[email]
            return False
            
        del self.email_otps[email]
        del self.email_sessions[session_id]
        return True
    
    async def verify_sms_otp(self, session_id: str, code: str) -> bool:
        """Verify SMS OTP code"""
        if session_id not in self.sms_sessions:
            return False
            
        phone_number = self.sms_sessions[session_id]["phone_number"]
        
        if phone_number not in self.sms_otps:
            return False
            
        if self.sms_otps[phone_number]["code"] != code:
            self.sms_otps[phone_number]["attempts"] += 1
            if self.sms_otps[phone_number]["attempts"] >= 5:
                del self.sms_otps[phone_number]
            return False
            
        del self.sms_otps[phone_number]
        del self.sms_sessions[session_id]
        return True


# Initialize OTP manager
otp_manager = OTPManager()


# Email OTP endpoints
@app.post("/auth/otp/email/request")
async def request_email_otp(email: str):
    """Request OTP for email"""
    session_id = await otp_manager.send_email_otp(email)
    return {"session_id": session_id}


@app.post("/auth/otp/email/verify")
async def verify_email_otp(session_id: str, code: str):
    """Verify email OTP and return JWT token"""
    if not await otp_manager.verify_email_otp(session_id, code):
        raise HTTPException(status_code=400, detail="Invalid OTP code")
    
    email = otp_manager.email_sessions.get(session_id, {}).get("email")
    if not email:
        raise HTTPException(status_code=400, detail="Session expired")
    
    async with async_session_maker() as session:
        user_db = SQLAlchemyUserDatabase(session, User)
        user = await user_db.get_by_email(email)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
    
    token = generate_jwt({"sub": str(user.id), "email": user.email}, SECRET_KEY, 3600)
    return {"access_token": token, "token_type": "bearer"}


# SMS OTP endpoints
@app.post("/auth/otp/sms/request")
async def request_sms_otp(phone_number: str):
    """Request OTP for phone number (via Melipayamak)"""
    session_id = await otp_manager.send_sms_otp(phone_number)
    return {"session_id": session_id}


@app.post("/auth/otp/sms/verify")
async def verify_sms_otp(session_id: str, code: str):
    """Verify SMS OTP and return JWT token"""
    if not await otp_manager.verify_sms_otp(session_id, code):
        raise HTTPException(status_code=400, detail="Invalid OTP code")
    
    phone_number = otp_manager.sms_sessions.get(session_id, {}).get("phone_number")
    if not phone_number:
        raise HTTPException(status_code=400, detail="Session expired")
    
    async with async_session_maker() as session:
        user_db = SQLAlchemyUserDatabase(session, User)
        user = await user_db.get_by_phone_number(phone_number)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
    
    token = generate_jwt({"sub": str(user.id), "phone_number": user.phone_number}, SECRET_KEY, 3600)
    return {"access_token": token, "token_type": "bearer"}


# Protected route
@app.get("/protected")
async def protected_route(user: User = Depends(fastapi_users.current_user(active=True))):
    return {"message": f"Hello, {user.email}!", "user_id": user.id}


# Create tables on startup
@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)