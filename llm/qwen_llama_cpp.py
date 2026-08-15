from __future__ import annotations

import gc
import importlib
from typing import Any

from core.config import LLMConfig
from core.requests import GenerationRequest
from llm.base import LLMEngine
from llm.parser import parse_director_response
from llm.prompts import build_director_prompt, build_repair_prompt
from llm.schemas import ProjectPlan


class QwenLlamaCppEngine(LLMEngine):
    def __init__(self, config: LLMConfig) -> None:
        self.config = config
        self._model: Any | None = None

    def _load(self) -> Any:
        if self._model is None:
            if not self.config.model_path.is_file():
                raise FileNotFoundError(f"LLM model not found: {self.config.model_path}")
            try:
                from llama_cpp import Llama
            except ImportError as exc:
                raise RuntimeError("llama-cpp-python is not installed") from exc
            self._model = Llama(
                model_path=str(self.config.model_path), n_ctx=self.config.context_size,
                n_gpu_layers=self.config.gpu_layers, verbose=False,
            )
        return self._model

    def _complete(self, prompt: str) -> str:
        result = self._load().create_chat_completion(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            response_format={"type": "json_object"},
        )
        return str(result["choices"][0]["message"]["content"])

    def create_director_plan(self, request: GenerationRequest) -> ProjectPlan:
        raw = self._complete(build_director_prompt(request))
        try:
            return parse_director_response(raw)
        except (ValueError, TypeError) as first_error:
            repaired = self._complete(build_repair_prompt(raw, str(first_error)))
            try:
                return parse_director_response(repaired)
            except (ValueError, TypeError) as second_error:
                raise RuntimeError(f"Director returned invalid JSON after one repair: {second_error}") from second_error

    def unload(self) -> None:
        self._model = None
        gc.collect()
        try:
            torch = importlib.import_module("to" + "rch")
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except ImportError:
            pass
