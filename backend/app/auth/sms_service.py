import aiohttp
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)

# Melipayamak REST API
# Docs: https://www.melipayamak.com/api/sendotp/
class SMSClient:
    async def send_otp(self, phone: str, code: str) -> bool:
        """
        Send OTP via Melipayamak SendOtp method.
        Returns True if recId received (success).
        """
        payload = aiohttp.FormData()
        payload.add_field("username", settings.MELIPAYAMAK_USERNAME)
        payload.add_field("password", settings.MELIPAYAMAK_PASSWORD)
        payload.add_field("from", settings.MELIPAYAMAK_FROM_NUMBER)
        payload.add_field("to", phone)
        payload.add_field("code", code)  # int, sent as string in form-data

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    settings.MELIPAYAMAK_SEND_OTP_URL,
                    data=payload,
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                ) as resp:
                    text = await resp.text()
                    # recId = success (positive number)
                    # 0 = wrong credentials, negative = error
                    try:
                        val = int(text.strip())
                        return val > 0
                    except ValueError:
                        logger.warning("SMS provider returned an invalid response")
                        return False
        except Exception:
            logger.exception("SMS provider request failed")
            return False


sms_client = SMSClient()
