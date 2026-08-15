from __future__ import annotations

from abc import ABC, abstractmethod

from core.requests import GenerationRequest
from llm.schemas import ProjectPlan


class LLMEngine(ABC):
    @abstractmethod
    def create_director_plan(self, request: GenerationRequest) -> ProjectPlan:
        raise NotImplementedError

    def unload(self) -> None:
        """Release model resources. Implementations may override."""
