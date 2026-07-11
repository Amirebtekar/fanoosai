import aiohttp
from app.core.config import settings

# Melipayamak REST API
# Docs: https://www.melipayamak.com/api/sendotp/
SEND_OTP_URL = "https://rest.payamak-panel.com/api/SendSMS/SendOtp"


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
                    SEND_OTP_URL,
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
                        print(f"SMS unexpected response: {text}")
                        return False
        except Exception as e:
            print(f"SMS error: {e}")
            return False


sms_client = SMSClient()
