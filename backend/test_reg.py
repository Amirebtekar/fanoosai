import httpx
import asyncio

async def test():
    async with httpx.AsyncClient() as client:
        # Register
        r = await client.post("http://localhost:8000/auth/otp/sms/register", json={
            "phone": "09123456789",
            "first_name": "Ali",
            "last_name": "Rezaei"
        })
        print("Register:", r.status_code, r.text)

asyncio.run(test())