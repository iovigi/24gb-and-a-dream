import pytest
from pydantic import ValidationError

from llm.mock import MockLLMEngine
from core.requests import GenerationRequest


def test_director_schema_has_matching_duration() -> None:
    plan = MockLLMEngine().create_director_plan(GenerationRequest(prompt="A castle", duration_seconds=30))
    assert sum(scene.duration_seconds for scene in plan.scenes) == 30


def test_schema_rejects_duplicate_scene_ids() -> None:
    plan = MockLLMEngine().create_director_plan(GenerationRequest(prompt="A castle", duration_seconds=20))
    with pytest.raises(ValidationError):
        plan.__class__.model_validate({**plan.model_dump(), "scenes": [plan.scenes[0].model_dump()] * 2})


def test_manual_narration_is_preserved_exactly() -> None:
    text = "The future does not wait. Neither should you."
    request = GenerationRequest(prompt="Reveal", narration_mode="manual", narration_text=text)
    plan = MockLLMEngine().create_director_plan(request)
    assert "".join(scene.narrator.text for scene in plan.scenes) == text
