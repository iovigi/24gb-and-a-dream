from __future__ import annotations

import json

from llm.schemas import ProjectPlan


def parse_director_response(response: str) -> ProjectPlan:
    text = response.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1]).strip()
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("LLM response did not contain a JSON object") from None
        payload = json.loads(text[start : end + 1])
    return ProjectPlan.model_validate(payload)
