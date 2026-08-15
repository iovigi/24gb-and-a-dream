from __future__ import annotations

import argparse
import wave
from pathlib import Path

from piper import PiperVoice, SynthesisConfig


VOICE_MODELS = {
    ("bg", "female"): "bg_BG-dimitar-medium.onnx",
    ("bg", "male"): "bg_BG-dimitar-medium.onnx",
    ("en", "female"): "en_US-lessac-medium.onnx",
    ("en", "male"): "en_US-ryan-medium.onnx",
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Local Piper TTS adapter")
    parser.add_argument("--models-dir", type=Path, required=True)
    parser.add_argument("--language", choices=("bg", "en"), required=True)
    parser.add_argument("--voice", choices=("female", "male"), required=True)
    parser.add_argument("--speed", type=float, default=1.0)
    parser.add_argument("--text", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    model_path = args.models_dir / VOICE_MODELS[(args.language, args.voice)]
    if not model_path.is_file():
        raise FileNotFoundError(f"Piper voice model not found: {model_path}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    voice = PiperVoice.load(str(model_path), config_path=str(model_path) + ".json")
    synthesis = SynthesisConfig(length_scale=1.0 / args.speed)
    with wave.open(str(args.output), "wb") as wav_file:
        voice.synthesize_wav(args.text, wav_file, syn_config=synthesis)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
