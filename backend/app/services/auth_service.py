import hashlib
import secrets
import time

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.password import get_password_hash
from app.auth.sms_service import sms_client
from app.core.config import settings
from app.infrastructure.redis_client import get_redis
from app.repositories.user_repository import UserRepository
from redis.exceptions import RedisError


class OTPStore:
    """Redis-backed OTP state shared by all API instances."""

    @staticmethod
    def _key(prefix: str, phone: str) -> str:
        digest = hashlib.sha256(phone.encode()).hexdigest()
        return f"fanoosai:auth:{prefix}:{digest}"

    def __init__(self) -> None:
        self._local: dict[str, tuple[str, float]] = {}
        self._local_attempts: dict[str, int] = {}

    def _use_local(self) -> bool:
        return settings.DEBUG

    async def check_send_rate(self, phone: str) -> None:
        try:
            allowed = await get_redis().set(
                self._key("send-rate", phone), "1", ex=settings.OTP_SEND_COOLDOWN, nx=True
            )
        except RedisError:
            if not self._use_local():
                raise
            key = self._key("send-rate", phone)
            previous = self._local.get(key)
            allowed = previous is None or time.monotonic() - previous[1] >= settings.OTP_SEND_COOLDOWN
            if allowed:
                self._local[key] = ("1", time.monotonic())
        if not allowed:
            raise HTTPException(429, "Please wait before requesting another code")

    async def store(self, phone: str, code: str) -> None:
        try:
            redis = get_redis()
            await redis.set(self._key("otp", phone), code, ex=settings.OTP_TTL)
            await redis.delete(self._key("attempts", phone))
        except RedisError:
            if not self._use_local():
                raise
            self._local[self._key("otp", phone)] = (code, time.monotonic() + settings.OTP_TTL)
            self._local_attempts.pop(self._key("attempts", phone), None)

    async def check(self, phone: str, code: str) -> bool:
        redis = None
        try:
            redis = get_redis()
            stored = await redis.get(self._key("otp", phone))
        except RedisError:
            if not self._use_local():
                raise
            value = self._local.get(self._key("otp", phone))
            stored = value[0] if value and value[1] > time.monotonic() else None
        if not stored:
            return False
        if not secrets.compare_digest(stored, code):
            attempts_key = self._key("attempts", phone)
            try:
                if redis is None:
                    raise RedisError("Redis unavailable")
                attempts = await redis.incr(attempts_key)
                if attempts == 1:
                    await redis.expire(attempts_key, settings.OTP_TTL)
            except RedisError:
                if not self._use_local():
                    raise
                attempts = self._local_attempts.get(attempts_key, 0) + 1
                self._local_attempts[attempts_key] = attempts
            return False
        try:
            if redis is None:
                raise RedisError("Redis unavailable")
            await redis.delete(self._key("otp", phone), self._key("attempts", phone))
        except RedisError:
            if not self._use_local():
                raise
            self._local.pop(self._key("otp", phone), None)
            self._local_attempts.pop(self._key("attempts", phone), None)
        return True

    async def get_attempts(self, phone: str) -> int:
        try:
            return int(await get_redis().get(self._key("attempts", phone)) or 0)
        except RedisError:
            if not self._use_local():
                raise
            return self._local_attempts.get(self._key("attempts", phone), 0)

    async def clear(self, phone: str) -> None:
        try:
            await get_redis().delete(self._key("otp", phone), self._key("attempts", phone))
        except RedisError:
            if not self._use_local():
                raise
        self._local.pop(self._key("otp", phone), None)
        self._local_attempts.pop(self._key("attempts", phone), None)


otp_store = OTPStore()


class AuthService:
    def __init__(self, session: AsyncSession):
        self.user_repo = UserRepository(session)
        self.otp_store = otp_store

    @staticmethod
    def _is_dev_otp(phone: str) -> bool:
        return bool(
            settings.DEBUG
            and settings.DEV_OTP_PHONE
            and settings.DEV_OTP_CODE
            and phone == settings.DEV_OTP_PHONE
        )

    async def _store_dev_otp(self, phone: str) -> None:
        await self.otp_store.store(phone, settings.DEV_OTP_CODE)

    async def register_sms(self, phone: str, first_name: str, last_name: str, email: str | None) -> None:
        if not self._is_dev_otp(phone):
            await otp_store.check_send_rate(phone)

        user = await self.user_repo.get_by_phone(phone)
        if not user:
            user = await self.user_repo.create(
                phone=phone,
                email=email,
                first_name=first_name,
                last_name=last_name,
                hashed_password=get_password_hash("sms-only"),
                is_active=True,
            )

        if self._is_dev_otp(phone):
            await self._store_dev_otp(phone)
            return

        code = f"{secrets.randbelow(900000) + 100000}"
        await otp_store.store(phone, code)
        sent = await sms_client.send_otp(phone, code)
        if not sent:
            raise HTTPException(503, "SMS service is temporarily unavailable")

    async def request_sms(self, phone: str) -> None:
        if not self._is_dev_otp(phone):
            await otp_store.check_send_rate(phone)

        user = await self.user_repo.get_by_phone(phone)
        if not user:
            raise HTTPException(400, "User not found; please register first")

        if self._is_dev_otp(phone):
            await self._store_dev_otp(phone)
            return

        code = f"{secrets.randbelow(900000) + 100000}"
        await otp_store.store(phone, code)
        sent = await sms_client.send_otp(phone, code)
        if not sent:
            raise HTTPException(503, "SMS service is temporarily unavailable")

    async def verify_sms(self, phone: str, code: str) -> str:
        attempts = await otp_store.get_attempts(phone)
        if attempts >= settings.OTP_MAX_ATTEMPTS:
            await otp_store.clear(phone)
            raise HTTPException(429, "Too many attempts; request a new code")

        if not await otp_store.check(phone, code):
            remaining = settings.OTP_MAX_ATTEMPTS - attempts - 1
            if remaining <= 0:
                await otp_store.clear(phone)
                raise HTTPException(429, "Too many attempts; request a new code")
            raise HTTPException(400, f"Invalid code. {remaining} attempts remaining")

        user = await self.user_repo.get_by_phone(phone)
        if not user:
            raise HTTPException(404, "User not found")

        await self.user_repo.mark_verified(user)
        return user
