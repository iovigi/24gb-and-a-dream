"""Start ComfyUI from inside the application.

`run.ps1` does this for source runs, but the packaged executable has no
launcher, so a user double-clicking it would reach the first scene and only then
discover that nothing is listening on port 8188. This is the same sequence
(health check, hidden process, poll until ready) owned by the app.

An instance that is already running is never touched: it belongs to whoever
started it, and stopping it would kill a ComfyUI the user is using elsewhere.
"""

from __future__ import annotations

import subprocess
import threading
import time

import requests

from core.config import ComfyUIConfig
from utils.logging import get_logger, log_directory

_logger = get_logger("comfyui")


class ComfyUINotStarted(RuntimeError):
    pass


class ComfyUILauncher:
    def __init__(self, config: ComfyUIConfig) -> None:
        self.config = config
        self._process: subprocess.Popen | None = None
        self._log = None
        self._lock = threading.Lock()

    @property
    def started_by_us(self) -> bool:
        return self._process is not None

    def is_running(self) -> bool:
        try:
            response = requests.get(f"{self.config.http_url}/system_stats", timeout=2)
            return response.status_code == 200
        except requests.RequestException:
            return False

    def ensure_running(self, progress=None) -> bool:
        """Return True when this call started ComfyUI, False if it was already up."""
        with self._lock:
            if self.is_running():
                _logger.info("ComfyUI already running at %s", self.config.http_url)
                return False
            if not self.config.autostart:
                raise ComfyUINotStarted(
                    f"ComfyUI is not running at {self.config.http_url} and autostart is disabled. "
                    "Start it manually or set comfyui.autostart: true."
                )
            self._start()
            self._wait_until_ready(progress)
            return True

    def stop(self) -> None:
        """Stop ComfyUI only if this launcher started it."""
        with self._lock:
            process = self._process
            if process is None:
                return
            self._process = None
            if process.poll() is None:
                _logger.info("Stopping the ComfyUI instance we started (pid %s)", process.pid)
                _terminate_tree(process)
            self._close_log()

    # ----------------------------------------------------------------- #
    def _start(self) -> None:
        if not self.config.python.is_file():
            raise ComfyUINotStarted(f"ComfyUI runtime is missing: {self.config.python}")
        main_script = self.config.root / "main.py"
        if not main_script.is_file():
            raise ComfyUINotStarted(f"ComfyUI main.py is missing: {main_script}")

        log_path = log_directory() / "comfyui.log"
        self._log = open(log_path, "a", buffering=1, encoding="utf-8", errors="replace")
        self._log.write(f"\n===== {time.strftime('%Y-%m-%d %H:%M:%S')} | starting ComfyUI =====\n")
        command = [
            str(self.config.python), "main.py", "--disable-auto-launch",
            "--listen", self.config.host, "--port", str(self.config.port),
        ]
        _logger.info("Starting ComfyUI: %s", " ".join(command))
        _logger.info("ComfyUI log: %s", log_path)
        self._process = subprocess.Popen(
            command, cwd=str(self.config.root), stdin=subprocess.DEVNULL,
            stdout=self._log, stderr=subprocess.STDOUT,
            creationflags=(
                getattr(subprocess, "CREATE_NO_WINDOW", 0)
                | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            ),
        )

    def _wait_until_ready(self, progress=None) -> None:
        assert self._process is not None
        deadline = time.monotonic() + self.config.startup_timeout_seconds
        announced = 0
        while time.monotonic() < deadline:
            if self._process.poll() is not None:
                code = self._process.returncode
                self._close_log()
                self._process = None
                raise ComfyUINotStarted(
                    f"ComfyUI exited during startup with code {code}. "
                    f"See {log_directory() / 'comfyui.log'}"
                )
            if self.is_running():
                _logger.info("ComfyUI is ready at %s", self.config.http_url)
                return
            waited = int(self.config.startup_timeout_seconds - (deadline - time.monotonic()))
            if progress is not None and waited >= announced + 5:
                announced = waited
                progress(f"Starting ComfyUI… {waited}s")
            time.sleep(1)
        self.stop()
        raise ComfyUINotStarted(
            f"ComfyUI did not become ready within {self.config.startup_timeout_seconds}s. "
            f"See {log_directory() / 'comfyui.log'}"
        )

    def _close_log(self) -> None:
        if self._log is not None:
            try:
                self._log.close()
            finally:
                self._log = None


def _terminate_tree(process: subprocess.Popen) -> None:
    # ComfyUI spawns workers; terminate() would leave them holding VRAM.
    try:
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            check=False, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except OSError:
        process.terminate()
    try:
        process.wait(timeout=15)
    except subprocess.TimeoutExpired:
        process.kill()


_shared: ComfyUILauncher | None = None
_shared_lock = threading.Lock()


def shared_launcher(config: ComfyUIConfig) -> ComfyUILauncher:
    """One launcher per process: there is a single ComfyUI endpoint."""
    global _shared
    with _shared_lock:
        if _shared is None:
            _shared = ComfyUILauncher(config)
        return _shared


def stop_shared_launcher() -> None:
    """Called on application shutdown; a no-op unless we started ComfyUI."""
    with _shared_lock:
        if _shared is not None:
            _shared.stop()
