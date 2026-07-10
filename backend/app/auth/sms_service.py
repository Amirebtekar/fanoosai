import aiohttp
from app.core.config import settings


class MelipayamakClient:
    def __init__(self):
        self.base_url = settings.MELIPAYAMAK_BASE_URL
        self.username = settings.MELIPAYAMAK_USERNAME
        self.password = settings.MELIPAYAMAK_PASSWORD
        self.from_number = settings.MELIPAYAMAK_FROM_NUMBER

    async def send_otp(self, phone: str, otp_code: str) -> bool:
        """
        Send OTP code to phone number via Melipayamak API
        """
        url = f"{self.base_url}/sms/send"

        message = f"فانووس‌ای‌آی: کد تأیید شما: {otp_code}"
        
        payload = {
            "username": self.username,
            "password": self.password,
            "from": self.from_number,
            "to": phone,
            "message": message,
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload) as response:
                    data = await response.json()
                    if response.status == 200 and data.get("success", False):
                        return True
                    else:
                        print(f"SMS API Error: {data}")
                        return False
        except Exception as e:
            print(f"SMS sending error: {e}")
            return False


# Singleton instance
melipayamak_client = MelipayamakClient()