"""Central crash diagnostics.

The app mixes Python, Qt, llama.cpp, torch/CUDA and ffmpeg. When any of the
native pieces dies, the process can disappear without a Python traceback and
without anything on screen. This module makes every death leave evidence:

* ``logs/app.log``      - the central rotating session log (see utils.logging)
* ``logs/crash.log``    - native faults (access violation / segfault / abort)
                          and every unhandled Python exception, with a header
* ``logs/console.log``  - raw stdout/stderr, including output printed by native
                          libraries that never reaches the logging module
* ``logs/session.json`` - marker telling whether the previous run exited cleanly
"""

from __future__ import annotations

import atexit
import datetime as _dt
import faulthandler
import io
import json
import logging
import os
import platform
import signal
import sys
import threading
import traceback
from pathlib import Path
from typing import Any, TextIO

from utils.logging import LOGGER_NAME, log_directory

_logger = logging.getLogger(f"{LOGGER_NAME}.crash")

_crash_stream: TextIO | None = None
_console_stream: TextIO | None = None
_session_file: Path | None = None
_installed = False
_last_activity = "startup"
_fatal_reason: str | None = None
_previous_session: dict[str, Any] | None = None
_activity_lock = threading.Lock()

_UNCLEAN_STATES = {"running", "fatal", "signal"}

# Qt reports these as plain warnings, but each one means Qt's internal state has
# already been damaged by a cross-thread call; an access violation usually follows.
_THREAD_AFFINITY_MARKERS = (
    "different thread",
    "Cannot create children",
    "Cannot send events to objects owned by",
    "is not the object's thread",
    "QObject::moveToThread",
)


# --------------------------------------------------------------------------- #
# public helpers
# --------------------------------------------------------------------------- #
def crash_log_path() -> Path:
    return log_directory() / "crash.log"


def note_activity(description: str) -> None:
    """Record what the app is doing, so a hard crash report says where it died."""
    global _last_activity
    with _activity_lock:
        _last_activity = description
    _logger.debug("Activity: %s", description)
    if _session_file is not None:
        _write_session_marker("running", activity=description)


def install(app_root: Path | None = None) -> Path:
    """Install every crash hook. Safe to call once, early in ``main()``.

    Returns the path of the crash log.
    """
    global _installed, _crash_stream, _console_stream, _session_file, _previous_session

    directory = log_directory(app_root)
    crash_path = directory / "crash.log"
    if _installed:
        return crash_path

    # 1. Native faults: keep a dedicated, unbuffered handle open for the whole
    #    process lifetime. faulthandler writes to the raw fd, so it still works
    #    when the interpreter state is already broken.
    _crash_stream = open(crash_path, "a", buffering=1, encoding="utf-8", errors="replace")
    faulthandler.enable(file=_crash_stream, all_threads=True)
    if hasattr(faulthandler, "register") and hasattr(signal, "SIGABRT"):
        try:
            faulthandler.register(signal.SIGABRT, file=_crash_stream, all_threads=True, chain=True)
        except (RuntimeError, ValueError, OSError):
            pass
    os.environ.setdefault("PYTHONFAULTHANDLER", "1")

    # 2. Mirror stdout/stderr into a file so native library output survives.
    _console_stream = open(
        directory / "console.log", "a", buffering=1, encoding="utf-8", errors="replace",
    )
    sys.stdout = _Tee(sys.stdout, _console_stream)
    sys.stderr = _Tee(sys.stderr, _console_stream)

    # 3. Python-level hooks.
    sys.excepthook = _excepthook
    threading.excepthook = _thread_excepthook
    if hasattr(sys, "unraisablehook"):
        sys.unraisablehook = _unraisablehook

    # 4. Termination signals (Ctrl+C, taskkill, console close).
    for name in ("SIGTERM", "SIGINT", "SIGBREAK"):
        signal_number = getattr(signal, name, None)
        if signal_number is None:
            continue
        try:
            signal.signal(signal_number, _signal_handler)
        except (ValueError, OSError):
            pass

    # 5. Clean-exit marker; its absence next run means the process was killed.
    _session_file = directory / "session.json"
    _previous_session = _read_session_marker(_session_file)
    _installed = True
    _write_session_marker("running", activity="startup")
    atexit.register(_on_exit)

    _write_crash_header("SESSION START")
    _log_environment()
    if _previous_session and _previous_session.get("state") in _UNCLEAN_STATES:
        _logger.critical(
            "PREVIOUS SESSION DID NOT EXIT CLEANLY (state=%s, started %s, last activity: %s, reason: %s). "
            "Check %s for a native fault report.",
            _previous_session.get("state"), _previous_session.get("started"),
            _previous_session.get("activity"), _previous_session.get("reason", "unknown"), crash_path,
        )
        _write_crash_header(
            f"PREVIOUS SESSION CRASHED (state={_previous_session.get('state')}) "
            f"- last activity: {_previous_session.get('activity')}"
        )
    return crash_path


def previous_session_crashed() -> bool:
    """True when the previous run was killed or died on an unhandled error.

    Safe to call after :func:`install`, which snapshots the marker before
    overwriting it for the current session.
    """
    data = _previous_session if _installed else _read_session_marker(log_directory() / "session.json")
    return bool(data and data.get("state") in _UNCLEAN_STATES)


def previous_session_details() -> dict[str, Any] | None:
    return dict(_previous_session) if _previous_session else None


def install_qt_message_handler() -> None:
    """Route Qt's own warnings/fatals into the central log.

    Must be called after PySide6 is importable; a ``qFatal`` aborts the process
    immediately, so capturing it is the only way to see why the window died.
    """
    try:
        from PySide6.QtCore import QtMsgType, qInstallMessageHandler
    except Exception:  # pragma: no cover - Qt missing in headless tests
        return

    levels = {
        QtMsgType.QtDebugMsg: logging.DEBUG,
        QtMsgType.QtInfoMsg: logging.INFO,
        QtMsgType.QtWarningMsg: logging.WARNING,
        QtMsgType.QtCriticalMsg: logging.ERROR,
        QtMsgType.QtFatalMsg: logging.CRITICAL,
    }
    qt_logger = logging.getLogger(f"{LOGGER_NAME}.qt")

    def handler(mode: Any, context: Any, message: str) -> None:
        level = levels.get(mode, logging.INFO)
        where = ""
        if getattr(context, "file", None):
            where = f" ({context.file}:{context.line})"
        if any(marker in message for marker in _THREAD_AFFINITY_MARKERS):
            # Qt only warns, but the process is already corrupted and normally
            # dies with an access violation seconds later, somewhere unrelated.
            # Capture the stacks now, while they still point at the real cause.
            qt_logger.critical(
                "CROSS-THREAD Qt ACCESS (last activity: %s) - Qt state is now unsafe "
                "and the process may die with an access violation: %s%s",
                _last_activity, message, where,
            )
            _write_crash_header(f"CROSS-THREAD Qt ACCESS - last activity: {_last_activity}")
            _write_crash(message)
            _dump_all_threads()
            _flush()
            return
        qt_logger.log(level, "%s%s", message, where)
        if mode == QtMsgType.QtFatalMsg:
            _write_crash_header("Qt FATAL: " + message)
            _dump_all_threads()
            _flush()

    qInstallMessageHandler(handler)


def log_exception(exc: BaseException, context: str = "") -> None:
    """Log an exception with its full traceback into both logs."""
    text = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    _logger.critical("%s\n%s", context or "Unhandled exception", text)
    _write_crash_header(context or "Unhandled exception")
    _write_crash(text)


# --------------------------------------------------------------------------- #
# hooks
# --------------------------------------------------------------------------- #
def _excepthook(exc_type, exc_value, exc_tb) -> None:
    global _fatal_reason
    if issubclass(exc_type, KeyboardInterrupt):
        _logger.warning("Interrupted by user (Ctrl+C)")
        _flush()
        return
    _fatal_reason = f"{exc_type.__name__}: {exc_value}"
    text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    _logger.critical("UNHANDLED EXCEPTION in main thread (last activity: %s)\n%s", _last_activity, text)
    _write_crash_header(f"UNHANDLED EXCEPTION - last activity: {_last_activity}")
    _write_crash(text)
    _dump_all_threads()
    _flush()


def _thread_excepthook(args) -> None:
    if issubclass(args.exc_type, SystemExit):
        return
    text = "".join(traceback.format_exception(args.exc_type, args.exc_value, args.exc_traceback))
    name = getattr(args.thread, "name", "?")
    _logger.critical("UNHANDLED EXCEPTION in thread %s (last activity: %s)\n%s", name, _last_activity, text)
    _write_crash_header(f"UNHANDLED EXCEPTION in thread {name} - last activity: {_last_activity}")
    _write_crash(text)
    _flush()


def _unraisablehook(unraisable) -> None:
    text = "".join(
        traceback.format_exception(
            unraisable.exc_type, unraisable.exc_value, unraisable.exc_traceback,
        )
    )
    _logger.error("Unraisable exception in %r\n%s", unraisable.object, text)
    _write_crash(text)
    _flush()


def _signal_handler(signal_number: int, frame) -> None:
    name = signal.Signals(signal_number).name if signal_number in set(signal.Signals) else str(signal_number)
    _logger.critical("Received %s - shutting down (last activity: %s)", name, _last_activity)
    _write_crash_header(f"SIGNAL {name} - last activity: {_last_activity}")
    _dump_all_threads()
    _flush()
    _write_session_marker("signal", activity=_last_activity, signal=name)
    raise SystemExit(128 + signal_number)


def _on_exit() -> None:
    if _fatal_reason:
        _logger.critical("Session ended after a fatal error: %s", _fatal_reason)
        _write_crash_header(f"SESSION END (fatal: {_fatal_reason})")
        _write_session_marker("fatal", activity=_last_activity, reason=_fatal_reason)
    else:
        _logger.info("Session ended cleanly (last activity: %s)", _last_activity)
        _write_crash_header("SESSION END (clean)")
        _write_session_marker("clean_exit", activity=_last_activity)
    _flush()


# --------------------------------------------------------------------------- #
# internals
# --------------------------------------------------------------------------- #
class _Tee(io.TextIOBase):
    """Write-through stream duplicating output into the console log file."""

    def __init__(self, primary: TextIO | None, mirror: TextIO) -> None:
        self._primary = primary
        self._mirror = mirror

    def write(self, text: str) -> int:  # type: ignore[override]
        if self._primary is not None:
            try:
                self._primary.write(text)
            except Exception:
                pass
        try:
            self._mirror.write(text)
        except Exception:
            pass
        return len(text)

    def flush(self) -> None:  # type: ignore[override]
        for stream in (self._primary, self._mirror):
            if stream is None:
                continue
            try:
                stream.flush()
            except Exception:
                pass

    def isatty(self) -> bool:  # type: ignore[override]
        return bool(self._primary is not None and self._primary.isatty())

    def fileno(self) -> int:  # type: ignore[override]
        if self._primary is None:
            raise io.UnsupportedOperation("fileno")
        return self._primary.fileno()

    @property
    def encoding(self) -> str:  # type: ignore[override]
        return getattr(self._primary, "encoding", "utf-8") or "utf-8"


def _write_crash(text: str) -> None:
    if _crash_stream is None:
        return
    try:
        _crash_stream.write(text if text.endswith("\n") else text + "\n")
        _crash_stream.flush()
    except Exception:
        pass


def _write_crash_header(title: str) -> None:
    stamp = _dt.datetime.now().isoformat(timespec="seconds")
    _write_crash(f"\n{'=' * 78}\n{stamp} | pid {os.getpid()} | {title}\n{'=' * 78}")


def _dump_all_threads() -> None:
    if _crash_stream is None:
        return
    try:
        _crash_stream.write("--- all thread stacks ---\n")
        faulthandler.dump_traceback(file=_crash_stream, all_threads=True)
        _crash_stream.flush()
    except Exception:
        pass


def _flush() -> None:
    for handler in logging.getLogger().handlers:
        try:
            handler.flush()
        except Exception:
            pass
    for stream in (_crash_stream, _console_stream):
        if stream is not None:
            try:
                stream.flush()
            except Exception:
                pass


def _write_session_marker(state: str, **extra: Any) -> None:
    if _session_file is None:
        return
    payload = {
        "state": state,
        "pid": os.getpid(),
        "updated": _dt.datetime.now().isoformat(timespec="seconds"),
        **extra,
    }
    if state == "running":
        payload.setdefault("started", payload["updated"])
    try:
        _session_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except Exception:
        pass


def _read_session_marker(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _log_environment() -> None:
    _logger.info("=== 24GB and a Dream session start ===")
    _logger.info("pid=%s python=%s", os.getpid(), sys.version.replace("\n", " "))
    _logger.info("platform=%s %s", platform.platform(), platform.machine())
    _logger.info("executable=%s frozen=%s", sys.executable, getattr(sys, "frozen", False))
    _logger.info("cwd=%s", Path.cwd())
    _logger.info("argv=%s", sys.argv)
    for module_name in ("PySide6", "torch", "llama_cpp", "pydantic", "requests"):
        _logger.info("package %s=%s", module_name, _version_of(module_name))
    _logger.info("CUDA: %s", _cuda_summary())


def _version_of(module_name: str) -> str:
    try:
        from importlib.metadata import version

        return version(module_name)
    except Exception:
        pass
    # Frozen builds may ship without dist-info metadata. Fall back to an already
    # imported module's own attribute; never import anything just to read it.
    module = sys.modules.get(module_name)
    for attribute in ("__version__", "VERSION"):
        value = getattr(module, attribute, None)
        if value:
            return str(value)
    return "not installed"


def _cuda_summary() -> str:
    try:
        from utils.gpu import gpu_summary

        return gpu_summary()
    except Exception as exc:  # pragma: no cover - diagnostics must never fail
        return f"unavailable ({exc})"
