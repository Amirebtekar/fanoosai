import json
import logging

import aiohttp
from app.core.config import settings

logger = logging.getLogger(__name__)

# Melipayamak REST API
# Docs: https://www.melipayamak.com/api/sendotp/
class SMSClient:
    @staticmethod
    def _is_success_response(raw: str) -> bool:
        value = raw.strip().lstrip("\ufeff")
        try:
            return int(value) > 0
        except ValueError:
            pass

        try:
            payload = json.loads(value)
        except (TypeError, json.JSONDecodeError):
            return False

        if not isinstance(payload, dict):
            return False
        for key in ("recId", "rec_id", "messageId", "message_id"):
            candidate = payload.get(key)
            if candidate is not None:
                try:
                    return int(candidate) > 0
                except (TypeError, ValueError):
                    return False
        return False

    async def send_otp(self, phone: str, code: str) -> bool:
        """
        Send OTP via Melipayamak SendOtp method.
        Returns True if recId received (success).
        """
        payload = {
            "username": settings.MELIPAYAMAK_USERNAME,
            "password": settings.MELIPAYAMAK_PASSWORD,
            "from": settings.MELIPAYAMAK_FROM_NUMBER,
            "to": phone,
            "code": code,
        }

        try:
            timeout = aiohttp.ClientTimeout(total=15)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    settings.MELIPAYAMAK_SEND_OTP_URL,
                    data=payload,
                ) as resp:
                    text = await resp.text()
                    success = resp.status < 400 and self._is_success_response(text)
                    if not success:
                        logger.warning(
                            "SMS provider rejected request",
                            extra={"status_code": resp.status, "response_length": len(text)},
                        )
                    return success
        except Exception:
            logger.exception("SMS provider request failed")
            return False


sms_client = SMSClient()
