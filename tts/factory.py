from core.config import TTSConfig
from tts.base import TTSEngine
from tts.local import BulgarianTTSEngine, EnglishTTSEngine
from tts.mock import MockTTSEngine


class TTSEngineFactory:
    @staticmethod
    def create(config: TTSConfig, language: str) -> TTSEngine:
        if language not in {"bg", "en"}:
            raise ValueError(f"Unsupported TTS language: {language}")
        language_config = config.bg if language == "bg" else config.en
        if language_config.backend == "mock":
            return MockTTSEngine()
        if language_config.backend in {"local", "bulgarian_local", "english_local"}:
            return BulgarianTTSEngine(language_config) if language == "bg" else EnglishTTSEngine(language_config)
        raise ValueError(f"Unsupported {language} TTS backend: {language_config.backend}")
