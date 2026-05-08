"""Shared helpers for runnable Coryl examples."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from textwrap import dedent

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"


def ensure_src_path() -> None:
    """Make local examples runnable from a source checkout."""

    if str(SRC_ROOT) not in sys.path:
        sys.path.insert(0, str(SRC_ROOT))


def emit_json(payload: object) -> int:
    """Print a stable JSON payload for tests and human inspection."""

    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


def write_text(path: Path, content: str) -> None:
    """Write text after creating parent directories."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def write_block(path: Path, content: str) -> None:
    """Write a dedented block with a trailing newline."""

    write_text(path, dedent(content).strip() + "\n")


def write_bytes(path: Path, content: bytes) -> None:
    """Write bytes after creating parent directories."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def pythonpath_env(*extra_paths: Path) -> dict[str, str]:
    """Build an environment that can import the local ``src`` tree."""

    env = os.environ.copy()
    parts = [str(path) for path in extra_paths]
    parts.append(str(SRC_ROOT))
    existing = env.get("PYTHONPATH")
    if existing:
        parts.append(existing)
    env["PYTHONPATH"] = os.pathsep.join(parts)
    return env
