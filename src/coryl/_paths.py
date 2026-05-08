"""Internal helpers for Coryl's managed-path safety rules."""

from __future__ import annotations

from pathlib import Path, PurePath, PurePosixPath
from typing import Literal

from .exceptions import CorylPathError, CorylUnsafePathError

ManagedPath = Path | PurePosixPath
PathStyle = Literal["local", "posix"]


def validate_managed_path_input(
    path_value: str | PurePath,
    *,
    allow_absolute: bool = False,
    path_style: PathStyle = "local",
) -> ManagedPath:
    """Validate a user-provided path before resolving it against a root."""

    raw_path = _coerce_managed_path(path_value, path_style=path_style)

    if _has_unsupported_anchor(raw_path):
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
    path_value: str | PurePath,
    *,
    base_path: str | PurePath,
    allowed_root: str | PurePath,
    allow_absolute: bool = False,
    path_style: PathStyle | None = None,
) -> ManagedPath:
    """Resolve a managed path while enforcing Coryl's root-confinement rules."""

    style = path_style or _managed_path_style(base_path)
    raw_path = validate_managed_path_input(
        path_value,
        allow_absolute=allow_absolute,
        path_style=style,
    )
    base = _normalize_managed_path(base_path, path_style=style)
    root = _normalize_managed_path(allowed_root, path_style=style)
    candidate = raw_path if raw_path.is_absolute() else base / raw_path
    resolved = _normalize_managed_path(candidate, path_style=style)

    if not is_within_root(resolved, root, path_style=style):
        raise CorylUnsafePathError(
            f"Path '{resolved}' escapes the allowed root '{root}'."
        )

    return resolved


def is_within_root(
    child: str | PurePath,
    parent: str | PurePath,
    *,
    path_style: PathStyle | None = None,
) -> bool:
    """Return ``True`` when ``child`` resolves inside ``parent``."""

    style = path_style or _managed_path_style(parent)
    child_path = _normalize_managed_path(child, path_style=style)
    parent_path = _normalize_managed_path(parent, path_style=style)
    return child_path == parent_path or child_path.is_relative_to(parent_path)


def _normalize_managed_path(
    path_value: str | PurePath,
    *,
    path_style: PathStyle,
) -> ManagedPath:
    if path_style == "local":
        return Path(path_value).resolve(strict=False)
    return _coerce_managed_path(path_value, path_style="posix")


def _coerce_managed_path(
    path_value: str | PurePath,
    *,
    path_style: PathStyle,
) -> ManagedPath:
    if path_style == "local":
        return Path(path_value)

    raw_text = (
        path_value.as_posix() if isinstance(path_value, PurePath) else str(path_value)
    )
    return PurePosixPath(raw_text.replace("\\", "/"))


def _managed_path_style(path_value: str | PurePath) -> PathStyle:
    return "local" if isinstance(path_value, Path) else "posix"


def _has_unsupported_anchor(path: ManagedPath) -> bool:
    if isinstance(path, Path):
        return bool(path.anchor and not path.is_absolute())

    return "://" in path.as_posix() or bool(path.parts and path.parts[0].endswith(":"))


def _has_parent_reference(path: PurePath) -> bool:
    return any(part == ".." for part in path.parts)
