import aiohttp

from app.core.config import settings

class AIService:
    async def run_prompt(
        self,
        model_key: str,
        prompt_text: str,
        response_format: dict | None = None,
    ) -> str:
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        if settings.AI_GATEWAY_API_KEY:
            headers["Authorization"] = f"Bearer {settings.AI_GATEWAY_API_KEY}"

        url = f"{settings.AI_GATEWAY_BASE_URL.rstrip('/')}/v1/chat/completions"
        payload = {
            "model": model_key,
            "messages": [{"role": "user", "content": prompt_text}],
            "temperature": 0.7,
            "max_tokens": 5000,
            
        }
        if response_format is not None:
            payload["response_format"] = response_format
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.post(url, json=payload, timeout=60) as response:
                body = await response.text()
                if response.status >= 400:
                    raise ValueError(body)
                return body
