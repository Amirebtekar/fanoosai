import pytest

from app.services.brand_extraction_service import (
    BrandExtractionService,
    BrandExtractionValidationError,
)

class FakeGateway:
    async def run_prompt(self, model_key: str, prompt_text: str, response_format=None) -> str:
        assert model_key == "extractor-model"
        assert "Original AI response" in prompt_text
        assert response_format["json_schema"]["name"] == "brand_extraction"
        return '{"brands":[{"rank":1,"name":"Parspack","domain":"parspack.com","confidence":0.99}]}'

@pytest.mark.asyncio
async def test_extracts_openai_chat_completion_envelope():
    class EnvelopeGateway:
        async def run_prompt(self, model_key, prompt_text, response_format=None):
            return '{"choices":[{"message":{"content":"{\\"brands\\":[{\\"rank\\":1,\\"name\\":\\"Parspack\\",\\"domain\\":null,\\"confidence\\":0.99}]}"}}]}'

    result = await BrandExtractionService(EnvelopeGateway()).extract("response")

    assert result.brands[0].name == "Parspack"

@pytest.mark.asyncio
async def test_accepts_top_level_brand_array():
    class ArrayGateway:
        async def run_prompt(self, model_key, prompt_text, response_format=None):
            return '[{"rank":1,"name":"Parspack","domain":null,"confidence":0.99}]'

    result = await BrandExtractionService(ArrayGateway()).extract("response")

    assert result.brands[0].name == "Parspack"

@pytest.mark.asyncio
async def test_extracts_and_validates_brands_without_persistence():
    result = await BrandExtractionService(FakeGateway()).extract("Parspack was recommended")

    assert result.brands[0].name == "Parspack"
    assert result.brands[0].rank == 1
    assert result.brands[0].domain == "parspack.com"

@pytest.mark.asyncio
@pytest.mark.parametrize("body", [
    '{"brands":"not-an-array"}',
    '{"brands":[{"rank":1,"name":"","domain":null,"confidence":0.5}]}',
    '{"brands":[{"rank":1,"name":"Brand","domain":"https://brand.com/x","confidence":0.5}]}',
    '{"brands":[{"rank":1,"name":"Brand","domain":null,"confidence":2}]}',
])
async def test_rejects_invalid_extraction(body):
    class InvalidGateway:
        async def run_prompt(self, model_key, prompt_text, response_format=None):
            return body

    with pytest.raises(BrandExtractionValidationError):
        await BrandExtractionService(InvalidGateway()).extract("response")
