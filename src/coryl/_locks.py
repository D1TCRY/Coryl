"""Internal optional file-locking helpers for Coryl."""

from __future__ import annotations

from contextlib import contextmanager
from importlib import import_module
from pathlib import Path
from typing import Any, Iterator

from .exceptions import CorylLockTimeoutError, CorylOptionalDependencyError


def lock_path_for(path: str | Path) -> Path:
    resource_path = Path(path)
    return resource_path.parent / f"{resource_path.name}.lock"


def _load_filelock_backend() -> tuple[type[Any], type[BaseException]]:
    try:
        module = import_module("filelock")
    except ModuleNotFoundError as error:
        raise CorylOptionalDependencyError(
            "Resource locking requires the optional 'filelock' dependency. "
            "Install it with 'pip install coryl[lock]'."
        ) from error

    try:
        file_lock_class = module.FileLock
        timeout_error = module.Timeout
    except AttributeError as error:  # pragma: no cover - defensive
        raise CorylOptionalDependencyError(
            "The installed 'filelock' package does not expose the expected locking API."
        ) from error

    return file_lock_class, timeout_error


@contextmanager
def managed_lock(path: str | Path, *, timeout: float | None = None) -> Iterator[Path]:
    file_lock_class, timeout_error = _load_filelock_backend()
    lock_path = lock_path_for(path)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    file_lock = file_lock_class(str(lock_path))

    try:
        acquire_context = (
            file_lock.acquire() if timeout is None else file_lock.acquire(timeout=timeout)
        )
        with acquire_context:
            yield lock_path
    except timeout_error as error:
        raise CorylLockTimeoutError(
            f"Timed out while waiting for lock '{lock_path}'."
        ) from error
