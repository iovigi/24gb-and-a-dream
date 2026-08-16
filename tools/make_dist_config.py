"""Generate the config.yaml that ships next to the packaged executable.

Relative paths in config.yaml resolve against the folder holding that file, and
`ffmpeg.binary` plus the TTS command are handed to subprocess, which resolves
them against the *current directory*. A plain copy therefore only works when the
executable happens to run from the repository root.

This rewrites the paths that point back into the repository (models, llama.cpp,
FFmpeg, the Piper runtime) as absolute, while leaving the folders that belong to
the deployment itself (`app.projects_dir`, `comfyui.workflows_dir`) relative.

Deploying to another machine means copying `runtime/` and `models/` beside the
executable and reverting those entries to relative paths.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import yaml

# Single values rewritten to absolute paths.
ABSOLUTE_FIELDS: tuple[tuple[str, ...], ...] = (
    ("llm", "model_path"),
    ("llm", "executable"),
    ("comfyui", "python"),
    ("comfyui", "root"),
    ("tts", "bg", "model_path"),
    ("tts", "en", "model_path"),
    ("ffmpeg", "binary"),
    ("ffmpeg", "ffprobe_binary"),
)

# Command lines whose relative entries point at repository files.
COMMAND_FIELDS: tuple[tuple[str, ...], ...] = (
    ("tts", "bg", "command"),
    ("tts", "en", "command"),
)

# Deliberately left relative: they belong to the deployment, not the repository.
DEPLOYMENT_LOCAL = (("app", "projects_dir"), ("comfyui", "workflows_dir"))


def absolute(root: Path, value: str) -> str:
    path = Path(value)
    return value if path.is_absolute() else str((root / path).resolve())


def rewrite(config: dict[str, Any], root: Path) -> list[str]:
    """Rewrite paths in place; returns a description of each change."""
    changes: list[str] = []
    for field in ABSOLUTE_FIELDS:
        section = _section(config, field[:-1])
        key = field[-1]
        if section is None or key not in section:
            continue
        rewritten = absolute(root, str(section[key]))
        if rewritten != section[key]:
            changes.append(f"{'.'.join(field)}: {section[key]} -> {rewritten}")
            section[key] = rewritten
    for field in COMMAND_FIELDS:
        section = _section(config, field[:-1])
        key = field[-1]
        if section is None or not section.get(key):
            continue
        rewritten_command = []
        for item in section[key]:
            text = str(item)
            # Only touch entries that name a real file; placeholders such as
            # "--language" or "{text}" must survive untouched.
            if text.startswith(("./", ".\\", "../", "..\\")) and (root / text).exists():
                rewritten_command.append(absolute(root, text))
                changes.append(f"{'.'.join(field)}: {text} -> {rewritten_command[-1]}")
            else:
                rewritten_command.append(text)
        section[key] = rewritten_command
    return changes


def _section(config: dict[str, Any], path: tuple[str, ...]) -> dict[str, Any] | None:
    current: Any = config
    for key in path:
        if not isinstance(current, dict) or key not in current:
            return None
        current = current[key]
    return current if isinstance(current, dict) else None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    root = args.source.resolve().parent
    config = yaml.safe_load(args.source.read_text(encoding="utf-8")) or {}
    changes = rewrite(config, root)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        yaml.safe_dump(config, sort_keys=False, allow_unicode=True, width=4096),
        encoding="utf-8",
    )
    print(f"Wrote {args.output} ({len(changes)} path(s) made absolute)")
    for change in changes:
        print(f"  {change}")
    for field in DEPLOYMENT_LOCAL:
        print(f"  kept relative: {'.'.join(field)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
