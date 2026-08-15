from __future__ import annotations

import os
import socket
import subprocess
import time

import requests

from core.config import LLMConfig
from core.requests import GenerationRequest
from llm.base import LLMEngine
from llm.parser import parse_director_response
from llm.prompts import build_director_prompt, build_repair_prompt
from llm.schemas import ProjectPlan


def _free_local_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


class QwenLlamaCliEngine(LLMEngine):
    """Runs a short-lived local llama.cpp server and releases VRAM after each completion."""

    def __init__(self, config: LLMConfig) -> None:
        self.config = config

    def _complete(self, prompt: str) -> str:
        server_executable = self.config.executable.with_name("llama-server.exe")
        if not server_executable.is_file():
            raise FileNotFoundError(f"llama.cpp server not found: {server_executable}")
        if not self.config.model_path.is_file():
            raise FileNotFoundError(f"LLM model not found: {self.config.model_path}")
        if "\n\nJSON SCHEMA:\n" in prompt:
            prompt = prompt.split("\n\nJSON SCHEMA:\n", 1)[0]

        port = _free_local_port()
        gpu_layers = "all" if self.config.gpu_layers < 0 else str(self.config.gpu_layers)
        command = [
            str(server_executable), "-m", str(self.config.model_path),
            "-c", str(self.config.context_size), "-ngl", gpu_layers,
            "--host", "127.0.0.1", "--port", str(port), "--parallel", "1",
        ]
        process = subprocess.Popen(
            command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=(
                getattr(subprocess, "CREATE_NO_WINDOW", 0)
                | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            ),
        )
        base_url = f"http://127.0.0.1:{port}"
        try:
            deadline = time.monotonic() + 90
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    raise RuntimeError(f"llama-server exited during startup with code {process.returncode}")
                try:
                    if requests.get(f"{base_url}/health", timeout=1).status_code == 200:
                        break
                except requests.RequestException:
                    pass
                time.sleep(0.25)
            else:
                raise TimeoutError("llama-server did not become ready within 90 seconds")

            response = requests.post(
                f"{base_url}/v1/chat/completions",
                json={
                    "model": self.config.model_path.name,
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "Return only JSON with this exact shape and every field: "
                                "{project:{title,duration_seconds,aspect_ratio,style,language},"
                                "voice_over:{enabled,language,voice,narration_mode},"
                                "scenes:[{id,duration_seconds,director:{visual_prompt,negative_prompt,"
                                "camera_motion,motion,preserve},narrator:{text,emotion,pace}}]}. "
                                "Scene durations must sum to project duration. motion and preserve "
                                "must be arrays containing strings only (never booleans or objects). "
                                "All other named values are strings except durations, id, and enabled."
                            ),
                        },
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.1,
                    "max_tokens": self.config.predict_tokens,
                    "chat_template_kwargs": {"enable_thinking": False},
                    "response_format": {"type": "json_object"},
                },
                timeout=300,
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            if not content:
                raise RuntimeError("Qwen returned an empty response")
            return str(content)
        finally:
            if process.poll() is None:
                if os.name == "nt":
                    subprocess.run(
                        ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL, check=False,
                        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                    )
                else:
                    process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)

    def create_director_plan(self, request: GenerationRequest) -> ProjectPlan:
        raw = self._complete(build_director_prompt(request))
        try:
            return parse_director_response(raw)
        except (ValueError, TypeError) as first_error:
            repaired = self._complete(build_repair_prompt(raw, str(first_error)))
            try:
                return parse_director_response(repaired)
            except (ValueError, TypeError) as second_error:
                raise RuntimeError(
                    f"Director returned invalid JSON after one repair: {second_error}"
                ) from second_error
