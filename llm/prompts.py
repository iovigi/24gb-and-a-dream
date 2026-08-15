from __future__ import annotations

import json

from core.requests import GenerationRequest
from llm.schemas import ProjectPlan

SYSTEM_PROMPT = """You are the director for a resource-constrained local video pipeline.
Return JSON only and follow the supplied JSON schema exactly. Respect duration and language.
Visual prompts should be in English. Keep scenes short and practical. If an image exists,
preserve its identity, architecture, composition, and important colors. Never rewrite manual
narration. Do not invent unsupported features. Scene durations must sum to project duration.
You are operating a financially constrained pipeline, not writing a novel."""


def build_director_prompt(request: GenerationRequest) -> str:
    payload = request.model_dump(mode="json")
    payload["reference_image"] = bool(request.reference_image)
    return (
        f"{SYSTEM_PROMPT}\n\nREQUEST:\n{json.dumps(payload, ensure_ascii=False, indent=2)}"
        f"\n\nJSON SCHEMA:\n{json.dumps(ProjectPlan.model_json_schema(), ensure_ascii=False)}"
    )


def build_repair_prompt(raw_response: str, error: str) -> str:
    return (
        "Repair the following response. Return JSON only, preserve all valid content, and fix "
        f"this validation error: {error}\n\nRESPONSE:\n{raw_response}"
    )
