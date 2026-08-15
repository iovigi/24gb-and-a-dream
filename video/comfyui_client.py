from __future__ import annotations

import shutil
import threading
import time
import uuid
from pathlib import Path
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from core.config import ComfyUIConfig


class ComfyUIError(RuntimeError):
    pass


class ComfyUIClient:
    def __init__(self, config: ComfyUIConfig) -> None:
        self.config = config
        self.client_id = str(uuid.uuid4())
        self.session = requests.Session()
        retry = Retry(total=3, backoff_factor=0.5, status_forcelist=(502, 503, 504), allowed_methods=("GET", "POST"))
        self.session.mount("http://", HTTPAdapter(max_retries=retry))

    def health_check(self) -> dict[str, Any]:
        try:
            response = self.session.get(f"{self.config.http_url}/system_stats", timeout=5)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as exc:
            raise ComfyUIError(f"ComfyUI is not reachable at {self.config.http_url}") from exc

    def upload_image(self, path: Path) -> str:
        with path.open("rb") as stream:
            response = self.session.post(
                f"{self.config.http_url}/upload/image",
                files={"image": (path.name, stream)}, data={"overwrite": "true"}, timeout=60,
            )
        response.raise_for_status()
        data = response.json()
        return str(Path(data.get("subfolder", "")) / data["name"]).replace("\\", "/")

    def submit_workflow(self, workflow: dict[str, Any]) -> str:
        try:
            response = self.session.post(
                f"{self.config.http_url}/prompt",
                json={"prompt": workflow, "client_id": self.client_id}, timeout=30,
            )
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as exc:
            raise ComfyUIError("Could not submit workflow to ComfyUI") from exc
        if data.get("node_errors"):
            raise ComfyUIError(f"ComfyUI rejected workflow: {data['node_errors']}")
        return str(data["prompt_id"])

    def wait_for_completion(self, prompt_id: str, cancel_event: threading.Event | None = None) -> dict[str, Any]:
        deadline = time.monotonic() + self.config.timeout_seconds
        while time.monotonic() < deadline:
            if cancel_event and cancel_event.is_set():
                self.cancel()
                raise InterruptedError("Video generation cancelled")
            try:
                response = self.session.get(f"{self.config.http_url}/history/{prompt_id}", timeout=15)
                response.raise_for_status()
                history = response.json()
            except requests.RequestException as exc:
                raise ComfyUIError("Could not read ComfyUI job history") from exc
            if prompt_id in history:
                job = history[prompt_id]
                status = job.get("status", {})
                if status.get("status_str") == "error" or status.get("completed") is False:
                    messages = status.get("messages", [])
                    if any(item and item[0] == "execution_error" for item in messages):
                        raise ComfyUIError(f"ComfyUI workflow failed: {messages}")
                if job.get("outputs"):
                    return job
            time.sleep(1)
        raise TimeoutError(f"ComfyUI job {prompt_id} timed out")

    def get_outputs(self, job: dict[str, Any]) -> list[dict[str, str]]:
        outputs: list[dict[str, str]] = []
        for node in job.get("outputs", {}).values():
            for kind in ("videos", "gifs", "images"):
                for item in node.get(kind, []):
                    outputs.append({
                        "filename": item["filename"], "subfolder": item.get("subfolder", ""),
                        "type": item.get("type", "output"),
                    })
        return outputs

    def download_output(self, output: dict[str, str], destination: Path) -> Path:
        response = self.session.get(f"{self.config.http_url}/view", params=output, stream=True, timeout=120)
        response.raise_for_status()
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("wb") as stream:
            shutil.copyfileobj(response.raw, stream)
        return destination

    def cancel(self) -> None:
        try:
            self.session.post(f"{self.config.http_url}/interrupt", timeout=5)
        except requests.RequestException:
            pass
