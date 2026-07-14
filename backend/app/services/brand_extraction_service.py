import json
import re
from dataclasses import dataclass
from typing import Any

from app.core.config import settings
from app.services.ai_service import AIService

EXTRACTION_PROMPT = """Extract brands from the original AI response below.
Preserve appearance order and assign ranks starting at 1. Include an official root
Domain only when highly confident; otherwise use null. Never guess a domain.
Return only valid JSON with this exact shape:
{"brands":[{"rank":1,"name":"Example","domain":null,"confidence":0.0}]}

Original AI response:
{response_text}
"""
_ROOT_DOMAIN = re.compile(r"^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$", re.I)


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
    def __init__(self, ai_gateway: AIService):
        self.ai_gateway = ai_gateway

    async def extract(self, response_text: str) -> ExtractionResult:
        prompt = EXTRACTION_PROMPT.format(response_text=response_text)
        raw = await self.ai_gateway.run_prompt(settings.BRAND_EXTRACTION_MODEL, prompt)
        return self._parse(raw)

    @staticmethod
    def _parse(raw: str) -> ExtractionResult:
        try:
            payload: Any = json.loads(raw)
        except (TypeError, json.JSONDecodeError) as exc:
            raise BrandExtractionValidationError("پاسخ استخراج JSON معتبر نیست") from exc

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
