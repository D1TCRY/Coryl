"""Internal file I/O helpers for Coryl."""

from __future__ import annotations

import os
import tempfile
from contextlib import suppress
from pathlib import Path


def _atomic_write_text(
    path: str | Path,
    text: str,
    encoding: str = "utf-8",
) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp_path = _temporary_path_for(destination)

    try:
        with temp_path.open("w", encoding=encoding) as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, destination)
        _fsync_parent_directory(destination)
    except Exception:
        _cleanup_temp_file(temp_path)
        raise

    return destination


def _atomic_write_bytes(path: str | Path, data: bytes) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp_path = _temporary_path_for(destination)

    try:
        with temp_path.open("wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, destination)
        _fsync_parent_directory(destination)
    except Exception:
        _cleanup_temp_file(temp_path)
        raise

    return destination


def _temporary_path_for(path: Path) -> Path:
    file_descriptor, temp_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    os.close(file_descriptor)
    return Path(temp_name)


def _cleanup_temp_file(path: Path) -> None:
    with suppress(FileNotFoundError):
        path.unlink()


def _fsync_parent_directory(path: Path) -> None:
    if os.name == "nt":
        return

    try:
        directory_fd = os.open(path.parent, os.O_RDONLY)
    except OSError:
        return

    try:
        os.fsync(directory_fd)
    except OSError:
        pass
    finally:
        os.close(directory_fd)
