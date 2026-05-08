"""Internal filesystem adapters for local paths and optional fsspec backends."""

from __future__ import annotations

import shutil
from importlib import import_module
from pathlib import Path, PurePath, PurePosixPath
from typing import Any, Literal

from ._paths import resolve_managed_path, validate_managed_path_input
from .exceptions import CorylOptionalDependencyError, CorylValidationError

FilesystemName = Literal["local", "fsspec"]


class LocalFS:
    """Small adapter over pathlib-backed local filesystem access."""

    kind: FilesystemName = "local"
    supports_atomic_writes = True
    supports_locks = True
    supports_watch = True

    def __init__(self, root: str | Path) -> None:
        self.root_path = Path(root).resolve(strict=False)

    def resolve(
        self,
        path_value: str | PurePath,
        *,
        base_path: str | PurePath,
        allowed_root: str | PurePath,
        allow_absolute: bool = False,
    ) -> Path:
        resolved = resolve_managed_path(
            path_value,
            base_path=base_path,
            allowed_root=allowed_root,
            allow_absolute=allow_absolute,
            path_style="local",
        )
        if not isinstance(resolved, Path):  # pragma: no cover - defensive
            raise TypeError("Local filesystem resolution returned a non-local path.")
        return resolved

    def exists(self, path: str | PurePath) -> bool:
        return Path(path).exists()

    def is_file(self, path: str | PurePath) -> bool:
        return Path(path).is_file()

    def is_dir(self, path: str | PurePath) -> bool:
        return Path(path).is_dir()

    def mkdir(
        self,
        path: str | PurePath,
        *,
        parents: bool = True,
        exist_ok: bool = True,
    ) -> Path:
        candidate = Path(path)
        candidate.mkdir(parents=parents, exist_ok=exist_ok)
        return candidate

    def read_text(self, path: str | PurePath, *, encoding: str = "utf-8") -> str:
        return Path(path).read_text(encoding=encoding)

    def write_text(
        self, path: str | PurePath, text: str, *, encoding: str = "utf-8"
    ) -> Path:
        candidate = Path(path)
        candidate.parent.mkdir(parents=True, exist_ok=True)
        candidate.write_text(text, encoding=encoding)
        return candidate

    def read_bytes(self, path: str | PurePath) -> bytes:
        return Path(path).read_bytes()

    def write_bytes(self, path: str | PurePath, data: bytes) -> Path:
        candidate = Path(path)
        candidate.parent.mkdir(parents=True, exist_ok=True)
        candidate.write_bytes(data)
        return candidate

    def glob(self, pattern: str) -> list[Path]:
        return sorted(self.root_path.glob(pattern))

    def remove(self, path: str | PurePath) -> None:
        candidate = Path(path)
        if candidate.is_dir():
            shutil.rmtree(candidate)
            return
        candidate.unlink()

    def display_path(self, path: str | PurePath) -> str:
        return str(Path(path))


class FsspecFS:
    """Small adapter over an optional fsspec filesystem backend."""

    kind: FilesystemName = "fsspec"
    supports_atomic_writes = False
    supports_locks = False
    supports_watch = False

    def __init__(self, root: str | Path, *, protocol: str | None = None) -> None:
        fsspec = _load_fsspec_module()
        root_uri, detected_protocol = _normalize_fsspec_root(root, protocol=protocol)
        filesystem, backend_root = fsspec.core.url_to_fs(root_uri)

        self.protocol = detected_protocol
        self.root_uri = root_uri
        self._filesystem = filesystem
        logical_root = validate_managed_path_input(
            backend_root or "/",
            allow_absolute=True,
            path_style="posix",
        )
        if not isinstance(logical_root, PurePosixPath):  # pragma: no cover - defensive
            raise TypeError("fsspec filesystem root must resolve to a POSIX path.")
        self.root_path = logical_root

    def resolve(
        self,
        path_value: str | PurePath,
        *,
        base_path: str | PurePath,
        allowed_root: str | PurePath,
        allow_absolute: bool = False,
    ) -> PurePosixPath:
        resolved = resolve_managed_path(
            path_value,
            base_path=base_path,
            allowed_root=allowed_root,
            allow_absolute=allow_absolute,
            path_style="posix",
        )
        if not isinstance(resolved, PurePosixPath):  # pragma: no cover - defensive
            raise TypeError("fsspec filesystem resolution returned a non-POSIX path.")
        return resolved

    def exists(self, path: str | PurePath) -> bool:
        return bool(self._filesystem.exists(self._backend_path(path)))

    def is_file(self, path: str | PurePath) -> bool:
        return bool(self._filesystem.isfile(self._backend_path(path)))

    def is_dir(self, path: str | PurePath) -> bool:
        return bool(self._filesystem.isdir(self._backend_path(path)))

    def mkdir(
        self,
        path: str | PurePath,
        *,
        parents: bool = True,
        exist_ok: bool = True,
    ) -> PurePosixPath:
        candidate = self._coerce_logical_path(path)
        backend_path = self._backend_path(candidate)
        if parents:
            if hasattr(self._filesystem, "makedirs"):
                self._filesystem.makedirs(backend_path, exist_ok=exist_ok)
            else:
                self._filesystem.mkdir(backend_path, create_parents=True)
            return candidate

        try:
            self._filesystem.mkdir(backend_path, create_parents=False)
        except FileExistsError:
            if not exist_ok:
                raise
        return candidate

    def read_text(self, path: str | PurePath, *, encoding: str = "utf-8") -> str:
        with self._filesystem.open(
            self._backend_path(path), "rt", encoding=encoding
        ) as handle:
            return handle.read()

    def write_text(
        self,
        path: str | PurePath,
        text: str,
        *,
        encoding: str = "utf-8",
    ) -> PurePosixPath:
        candidate = self._coerce_logical_path(path)
        self.mkdir(candidate.parent, parents=True, exist_ok=True)
        with self._filesystem.open(
            self._backend_path(candidate), "wt", encoding=encoding
        ) as handle:
            handle.write(text)
        return candidate

    def read_bytes(self, path: str | PurePath) -> bytes:
        with self._filesystem.open(self._backend_path(path), "rb") as handle:
            return handle.read()

    def write_bytes(self, path: str | PurePath, data: bytes) -> PurePosixPath:
        candidate = self._coerce_logical_path(path)
        self.mkdir(candidate.parent, parents=True, exist_ok=True)
        with self._filesystem.open(self._backend_path(candidate), "wb") as handle:
            handle.write(data)
        return candidate

    def glob(self, pattern: str) -> list[PurePosixPath]:
        backend_pattern = self._backend_glob_pattern(pattern)
        matches = sorted(str(match) for match in self._filesystem.glob(backend_pattern))
        return [self._coerce_logical_path(match) for match in matches]

    def remove(self, path: str | PurePath) -> None:
        candidate = self._coerce_logical_path(path)
        self._filesystem.rm(
            self._backend_path(candidate), recursive=self.is_dir(candidate)
        )

    def display_path(self, path: str | PurePath) -> str:
        logical_path = self._coerce_logical_path(path)
        if logical_path == self.root_path:
            return self.root_uri

        relative = logical_path.relative_to(self.root_path).as_posix()
        return f"{self.root_uri.rstrip('/')}/{relative}"

    def _coerce_logical_path(self, path: str | PurePath) -> PurePosixPath:
        candidate = validate_managed_path_input(
            path,
            allow_absolute=True,
            path_style="posix",
        )
        if not isinstance(candidate, PurePosixPath):  # pragma: no cover - defensive
            raise TypeError("fsspec paths must normalize to POSIX logical paths.")
        return candidate

    def _backend_path(self, path: str | PurePath) -> str:
        return self._coerce_logical_path(path).as_posix()

    def _backend_glob_pattern(self, pattern: str) -> str:
        normalized = pattern.replace("\\", "/").strip()
        root_text = self.root_path.as_posix().rstrip("/")
        if normalized in {"", "."}:
            return root_text or "/"
        if normalized.startswith("/"):
            return normalized
        if root_text:
            return f"{root_text}/{normalized}"
        return f"/{normalized}"


def create_filesystem(
    root: str | Path,
    *,
    filesystem: str | None = None,
    protocol: str | None = None,
) -> LocalFS | FsspecFS:
    if filesystem is None or filesystem == "local":
        if protocol is not None:
            raise TypeError("protocol= is only supported when filesystem='fsspec'.")
        return LocalFS(root)
    if filesystem != "fsspec":
        raise CorylValidationError(
            "filesystem must be either 'local' or 'fsspec' when provided."
        )
    return FsspecFS(root, protocol=protocol)


def _normalize_fsspec_root(
    root: str | Path, *, protocol: str | None
) -> tuple[str, str]:
    root_text = str(root).strip()
    if not root_text:
        raise TypeError("fsspec-backed Coryl requires a non-empty root.")

    if "://" in root_text:
        detected_protocol = root_text.split("://", 1)[0]
        if protocol is not None and protocol != detected_protocol:
            raise CorylValidationError(
                f"fsspec protocol mismatch: root uses '{detected_protocol}' but protocol="
                f"{protocol!r} was provided."
            )
        return root_text, detected_protocol

    if protocol is None:
        raise TypeError(
            "fsspec-backed Coryl requires either protocol= or a fully-qualified root such as "
            "'memory://app'."
        )

    return f"{protocol}://{root_text.lstrip('/')}", protocol


def _load_fsspec_module() -> Any:
    try:
        return import_module("fsspec")
    except ModuleNotFoundError as error:
        raise CorylOptionalDependencyError(
            "Optional fsspec filesystem support requires the 'fsspec' dependency. "
            "Install it with 'pip install coryl[fsspec]'."
        ) from error
