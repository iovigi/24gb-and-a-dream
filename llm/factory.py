from core.config import LLMConfig
from llm.base import LLMEngine
from llm.mock import MockLLMEngine
from llm.qwen_llama_cpp import QwenLlamaCppEngine
from llm.qwen_llama_cli import QwenLlamaCliEngine


class LLMFactory:
    @staticmethod
    def create(config: LLMConfig) -> LLMEngine:
        if config.backend == "mock":
            return MockLLMEngine()
        if config.backend == "llama_cpp":
            return QwenLlamaCppEngine(config)
        if config.backend == "llama_cpp_cli":
            return QwenLlamaCliEngine(config)
        raise ValueError(f"Unsupported LLM backend: {config.backend}")
