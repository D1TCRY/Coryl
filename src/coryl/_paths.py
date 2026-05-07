"""Internal helpers for Coryl's managed-path safety rules."""

from __future__ import annotations

from pathlib import Path, PurePath

from .exceptions import CorylPathError, CorylUnsafePathError


def validate_managed_path_input(
    path_value: str | Path,
    *,
    allow_absolute: bool = False,
) -> Path:
    """Validate a user-provided path before resolving it against a root."""

    raw_path = Path(path_value)

    if raw_path.anchor and not raw_path.is_absolute():
        raise CorylPathError(
            f"Anchored paths are not supported for managed resources: '{raw_path}'."
        )
    if raw_path.is_absolute() and not allow_absolute:
        raise CorylPathError(
            f"Absolute paths are not allowed for managed resources: '{raw_path}'."
        )
    if _has_parent_reference(raw_path):
        raise CorylUnsafePathError(
            f"Path traversal is not allowed for managed resources: '{raw_path}'."
        )

    return raw_path


def resolve_managed_path(
    path_value: str | Path,
    *,
    base_path: str | Path,
    allowed_root: str | Path,
    allow_absolute: bool = False,
) -> Path:
    """Resolve a managed path while enforcing Coryl's root-confinement rules."""

    raw_path = validate_managed_path_input(path_value, allow_absolute=allow_absolute)
    base = Path(base_path).resolve(strict=False)
    root = Path(allowed_root).resolve(strict=False)
    candidate = raw_path if raw_path.is_absolute() else base / raw_path
    resolved = candidate.resolve(strict=False)

    if not is_within_root(resolved, root):
        raise CorylUnsafePathError(
            f"Path '{resolved}' escapes the allowed root '{root}'."
        )

    return resolved


def is_within_root(child: str | Path, parent: str | Path) -> bool:
    """Return ``True`` when ``child`` resolves inside ``parent``."""

    child_path = Path(child).resolve(strict=False)
    parent_path = Path(parent).resolve(strict=False)
    return child_path == parent_path or child_path.is_relative_to(parent_path)


def _has_parent_reference(path: PurePath) -> bool:
    return any(part == ".." for part in path.parts)
