import asyncio
import json

from app.services.ai_service import AIService


async def main() -> None:
    service = AIService()
    try:
        response = await service.run_prompt(
            "openai/gpt-5.1-chat",
            "What is today's most important OpenAI news? Include the source link.",
        )
        print(json.loads(response)["choices"][0]["message"]["content"])
    finally:
        await service.close()


if __name__ == "__main__":
    asyncio.run(main())
