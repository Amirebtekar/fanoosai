import json
import logging
import re
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.repositories.system_settings_repository import (
    EXTRACTION_MODEL_KEY,
    EXTRACTION_PROMPT_KEY,
    get_setting,
)
from app.services.ai_service import AIService

EXTRACTION_PROMPT = """Extract brands from the original AI response below.
Preserve appearance order and assign ranks starting at 1. Include an official root
Domain only when highly confident; otherwise use null. Never guess a domain.
Return only valid JSON with this exact shape:
{{"brands":[{{"rank":1,"name":"Example","domain":"example.com",confidence":1.0}}]}}

Original AI response:
{response_text}
"""
EXTRACTION_RESPONSE_FORMAT = {
    "type": "json_schema",
    "json_schema": {
        "name": "brand_extraction",
        "schema": {
            "type": "object",
            "properties": {
                "brands": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "rank": {"type": "integer"},
                            "name": {"type": "string"},
                            "domain": {"type": ["string", "null"]},
                            "confidence": {"type": "number"},
                        },
                        "required": ["rank", "name", "domain", "confidence"],
                    },
                },
            },
            "required": ["brands"],
        },
    },
}
_ROOT_DOMAIN = re.compile(r"^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$", re.I)
logger = logging.getLogger(__name__)

class BrandExtractionValidationError(ValueError):
    """The extraction model returned JSON outside the extraction contract."""

@dataclass(frozen=True)
class ExtractedBrand:
    rank: int
    name: str
    domain: str | None
    confidence: float

@dataclass(frozen=True)
class ExtractionResult:
    brands: list[ExtractedBrand]

class BrandExtractionService:
    def __init__(self, ai_gateway: AIService, session: AsyncSession | None = None):
        self.ai_gateway = ai_gateway
        self.session = session

    async def extract(self, response_text: str) -> ExtractionResult:
        prompt_template, model_key = await self._resolve_config()
        prompt = prompt_template.format(response_text=response_text)
        raw = await self.ai_gateway.run_prompt(
            model_key,
            prompt,
            response_format=EXTRACTION_RESPONSE_FORMAT,
        )
        return self._parse(raw)

    async def _resolve_config(self) -> tuple[str, str]:
        if self.session is None:
            return EXTRACTION_PROMPT, settings.BRAND_EXTRACTION_MODEL
        template = await get_setting(self.session, EXTRACTION_PROMPT_KEY, EXTRACTION_PROMPT)
        model = await get_setting(self.session, EXTRACTION_MODEL_KEY, settings.BRAND_EXTRACTION_MODEL)
        return template, model

    @staticmethod
    def _parse(raw: str) -> ExtractionResult:
        try:
            payload: Any = json.loads(raw)
        except (TypeError, json.JSONDecodeError) as exc:
            raise BrandExtractionValidationError("پاسخ استخراج JSON معتبر نیست") from exc

        if isinstance(payload, dict) and "choices" in payload:
            try:
                content = payload["choices"][0]["message"]["content"]
                payload = json.loads(content) if isinstance(content, str) else content
            except (IndexError, KeyError, TypeError, json.JSONDecodeError) as exc:
                raise BrandExtractionValidationError("ساختار پاسخ استخراج معتبر نیست") from exc

        if isinstance(payload, list):
            payload = {"brands": payload}

        if not isinstance(payload, dict) or not isinstance(payload.get("brands"), list):
            raise BrandExtractionValidationError("فیلد brands باید آرایه باشد")
        brands = []
        for item in payload["brands"]:
            if not isinstance(item, dict):
                raise BrandExtractionValidationError("هر برند باید یک شیء باشد")
            rank, name, domain, confidence = (item.get(key) for key in ("rank", "name", "domain", "confidence"))
            if isinstance(rank, bool) or not isinstance(rank, int):
                raise BrandExtractionValidationError("rank باید عدد صحیح باشد")
            if not isinstance(name, str) or not name.strip():
                raise BrandExtractionValidationError("name نباید خالی باشد")
            if domain is not None and (not isinstance(domain, str) or not _ROOT_DOMAIN.fullmatch(domain.strip())):
                raise BrandExtractionValidationError("domain باید Root Domain معتبر یا null باشد")
            if isinstance(confidence, bool) or not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
                raise BrandExtractionValidationError("confidence باید عددی بین صفر و یک باشد")
            brands.append(ExtractedBrand(rank, name.strip(), domain.strip() if domain else None, float(confidence)))
        return ExtractionResult(brands)
