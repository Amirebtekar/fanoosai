import pytest
from pydantic import ValidationError

from app.projects.schema import PromptCreate


def test_prompt_create_requires_at_least_one_model():
    with pytest.raises(ValidationError):
        PromptCreate(text="test")
    with pytest.raises(ValidationError):
        PromptCreate(text="test", model_ids=[])

    assert PromptCreate(text="test", model_ids=[1]).model_ids == [1]
