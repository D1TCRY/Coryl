"""Resource models used by Coryl."""

from __future__ import annotations

import shutil
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import IO, Literal

from ._io import _atomic_write_bytes, _atomic_write_text
from ._locks import managed_lock
from ._paths import is_within_root, resolve_managed_path, validate_managed_path_input
from .exceptions import (
    CorylValidationError,
    ResourceKindError,
    UnsafePathError,
    UnsupportedFormatError,
)
from .serialization import dump_to_path, load_from_path, structured_format_for_path

ResourceKind = Literal["file", "directory"]
ResourceRole = Literal["resource", "config", "cache", "assets"]
MISSING = object()


@dataclass(frozen=True, slots=True)
class ResourceSpec:
    """Declarative description of a managed resource."""

    relative_path: Path
    kind: ResourceKind = "file"
    create: bool = True
    encoding: str = "utf-8"
    role: ResourceRole = "resource"

    def __post_init__(self) -> None:
        relative_path = validate_managed_path_input(self.relative_path)
        if self.kind not in {"file", "directory"}:
            raise ResourceKindError("ResourceSpec.kind must be either 'file' or 'directory'.")
        if self.role not in {"resource", "config", "cache", "assets"}:
            raise CorylValidationError("ResourceSpec.role is invalid.")
        if self.role == "config" and self.kind != "file":
            raise CorylValidationError("Config resources must be files.")
        if self.role in {"cache", "assets"} and self.kind != "directory":
            raise CorylValidationError("Cache and asset resources must be directories.")
        object.__setattr__(self, "relative_path", relative_path)

    @classmethod
    def file(
        cls,
        path: str | Path,
        *,
        create: bool = True,
        encoding: str = "utf-8",
    ) -> "ResourceSpec":
        return cls(
            relative_path=Path(path),
            kind="file",
            create=create,
            encoding=encoding,
        )

    @classmethod
    def directory(
        cls,
        path: str | Path,
        *,
        create: bool = True,
        encoding: str = "utf-8",
    ) -> "ResourceSpec":
        return cls(
            relative_path=Path(path),
            kind="directory",
            create=create,
            encoding=encoding,
        )

    @classmethod
    def config(
        cls,
        path: str | Path,
        *,
        create: bool = True,
        encoding: str = "utf-8",
    ) -> "ResourceSpec":
        return cls(
            relative_path=Path(path),
            kind="file",
            create=create,
            encoding=encoding,
            role="config",
        )

    @classmethod
    def cache(
        cls,
        path: str | Path,
        *,
        create: bool = True,
        encoding: str = "utf-8",
    ) -> "ResourceSpec":
        return cls(
            relative_path=Path(path),
            kind="directory",
            create=create,
            encoding=encoding,
            role="cache",
        )

    @classmethod
    def assets(
        cls,
        path: str | Path,
        *,
        create: bool = True,
        encoding: str = "utf-8",
    ) -> "ResourceSpec":
        return cls(
            relative_path=Path(path),
            kind="directory",
            create=create,
            encoding=encoding,
            role="assets",
        )


@dataclass(slots=True)
class Resource:
    """Concrete resource bound to a resolved path."""

    name: str
    path: Path
    kind: ResourceKind
    create: bool = True
    encoding: str = "utf-8"
    role: ResourceRole = "resource"

    def __post_init__(self) -> None:
        self.path = self.path.resolve(strict=False)
        if self.kind not in {"file", "directory"}:
            raise ResourceKindError("Resource.kind must be either 'file' or 'directory'.")
        if self.role not in {"resource", "config", "cache", "assets"}:
            raise CorylValidationError("Resource.role is invalid.")
        if self.role == "config" and self.kind != "file":
            raise CorylValidationError("Config resources must be files.")
        if self.role in {"cache", "assets"} and self.kind != "directory":
            raise CorylValidationError("Cache and asset resources must be directories.")
        if self.create:
            self.ensure()

    def __fspath__(self) -> str:
        return str(self.path)

    def __str__(self) -> str:
        return str(self.path)

    @property
    def format(self) -> str | None:
        return structured_format_for_path(self.path)

    def ensure(self) -> Path:
        if self.kind == "directory":
            self.path.mkdir(parents=True, exist_ok=True)
            return self.path

        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.touch(exist_ok=True)
        return self.path

    def exists(self) -> bool:
        return self.path.exists()

    def is_file(self) -> bool:
        return self.path.is_file()

    def is_dir(self) -> bool:
        return self.path.is_dir()

    def open(self, *args: object, **kwargs: object) -> IO[str] | IO[bytes]:
        if self.kind != "file":
            raise ResourceKindError(f"Resource '{self.name}' is a directory, not a file.")
        return self.path.open(*args, **kwargs)

    def read_text(self, *, encoding: str | None = None) -> str:
        if self.kind != "file":
            raise ResourceKindError(f"Resource '{self.name}' is a directory, not a file.")
        return self.path.read_text(encoding=encoding or self.encoding)

    def write_text(
        self,
        content: str,
        *,
        encoding: str | None = None,
        atomic: bool = True,
    ) -> Path:
        if self.kind != "file":
            raise ResourceKindError(f"Resource '{self.name}' is a directory, not a file.")

        actual_encoding = encoding or self.encoding
        if atomic:
            return _atomic_write_text(self.path, content, encoding=actual_encoding)

        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(content, encoding=actual_encoding)
        return self.path

    def read_bytes(self) -> bytes:
        if self.kind != "file":
            raise ResourceKindError(f"Resource '{self.name}' is a directory, not a file.")
        return self.path.read_bytes()

    def write_bytes(self, content: bytes, *, atomic: bool = True) -> Path:
        if self.kind != "file":
            raise ResourceKindError(f"Resource '{self.name}' is a directory, not a file.")

        if atomic:
            return _atomic_write_bytes(self.path, content)

        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_bytes(content)
        return self.path

    def read_data(self, *, default: object = MISSING, encoding: str | None = None) -> object:
        return self._read_structured(default=default, encoding=encoding)

    def write_data(
        self,
        content: object,
        *,
        encoding: str | None = None,
        atomic: bool = True,
    ) -> Path:
        return self._write_structured(content, encoding=encoding, atomic=atomic)

    def read_json(self, *, default: object = MISSING, encoding: str | None = None) -> object:
        return self._read_structured(default=default, expected_format="json", encoding=encoding)

    def write_json(
        self,
        content: object,
        *,
        encoding: str | None = None,
        atomic: bool = True,
    ) -> Path:
        return self._write_structured(
            content,
            expected_format="json",
            encoding=encoding,
            atomic=atomic,
        )

    def read_toml(self, *, default: object = MISSING, encoding: str | None = None) -> object:
        return self._read_structured(default=default, expected_format="toml", encoding=encoding)

    def write_toml(
        self,
        content: object,
        *,
        encoding: str | None = None,
        atomic: bool = True,
    ) -> Path:
        return self._write_structured(
            content,
            expected_format="toml",
            encoding=encoding,
            atomic=atomic,
        )

    def read_yaml(self, *, default: object = MISSING, encoding: str | None = None) -> object:
        return self._read_structured(default=default, expected_format="yaml", encoding=encoding)

    def write_yaml(
        self,
        content: object,
        *,
        encoding: str | None = None,
        atomic: bool = True,
    ) -> Path:
        return self._write_structured(
            content,
            expected_format="yaml",
            encoding=encoding,
            atomic=atomic,
        )

    def content(self, *, default: object = MISSING) -> object:
        try:
            return self._auto_read()
        except Exception:
            if default is not MISSING:
                return default
            raise

    def write(self, content: object) -> Path:
        if self.kind != "file":
            raise ResourceKindError(f"Resource '{self.name}' is a directory, not a file.")

        if self.format is not None:
            return self.write_data(content)
        if isinstance(content, bytes):
            return self.write_bytes(content)
        return self.write_text(str(content))

    def joinpath(
        self,
        *parts: str | Path,
        kind: ResourceKind | None = None,
        create: bool = False,
        role: ResourceRole = "resource",
    ) -> "Resource":
        if self.kind != "directory":
            raise ResourceKindError(f"Resource '{self.name}' is a file, not a directory.")

        candidate = self._resolve_child_path(*parts)

        inferred_kind: ResourceKind = kind or ("file" if candidate.suffix else "directory")
        child_name = "/".join([self.name, *[str(part) for part in parts]])
        return create_resource(
            name=child_name,
            path=candidate,
            kind=inferred_kind,
            create=create,
            encoding=self.encoding,
            role=role,
        )

    def iterdir(self) -> Iterator[Path]:
        if self.kind != "directory":
            raise ResourceKindError(f"Resource '{self.name}' is a file, not a directory.")
        self.ensure()
        return self.path.iterdir()

    def glob(self, pattern: str) -> list[Path]:
        if self.kind != "directory":
            raise ResourceKindError(f"Resource '{self.name}' is a file, not a directory.")
        self.ensure()
        return sorted(self.path.glob(pattern))

    @contextmanager
    def lock(self, timeout: float | None = None) -> Iterator["Resource"]:
        with managed_lock(self.path, timeout=timeout):
            yield self

    def _auto_read(self) -> object:
        if self.format is not None:
            return self.read_data()
        return self.read_text()

    def _read_structured(
        self,
        *,
        default: object = MISSING,
        expected_format: str | None = None,
        encoding: str | None = None,
    ) -> object:
        if self.kind != "file":
            raise ResourceKindError(f"Resource '{self.name}' is a directory, not a file.")

        actual_format = self.format
        if actual_format is None:
            raise UnsupportedFormatError(
                f"Resource '{self.name}' is not a structured file. "
                "Supported formats are: .json, .toml, .yaml, .yml."
            )
        if expected_format is not None and actual_format != expected_format:
            raise UnsupportedFormatError(
                f"Resource '{self.name}' uses '{actual_format}', not '{expected_format}'."
            )

        try:
            raw_content = self.read_text(encoding=encoding)
            return load_from_path(self.path, raw_content)
        except Exception:
            if default is not MISSING:
                return default
            raise

    def _write_structured(
        self,
        content: object,
        *,
        expected_format: str | None = None,
        encoding: str | None = None,
        atomic: bool = True,
    ) -> Path:
        if self.kind != "file":
            raise ResourceKindError(f"Resource '{self.name}' is a directory, not a file.")

        actual_format = self.format
        if actual_format is None:
            raise UnsupportedFormatError(
                f"Resource '{self.name}' is not a structured file. "
                "Supported formats are: .json, .toml, .yaml, .yml."
            )
        if expected_format is not None and actual_format != expected_format:
            raise UnsupportedFormatError(
                f"Resource '{self.name}' uses '{actual_format}', not '{expected_format}'."
            )

        payload = dump_to_path(self.path, content)
        return self.write_text(payload, encoding=encoding, atomic=atomic)

    def _assert_inside(self, candidate: Path) -> None:
        if not is_within_root(candidate, self.path):
            raise UnsafePathError("Joined path escapes the directory resource root.")

    def _resolve_child_path(self, *parts: str | Path) -> Path:
        return resolve_managed_path(
            Path(*parts),
            base_path=self.path,
            allowed_root=self.path,
        )


class ConfigResource(Resource):
    """Structured configuration file with load/save helpers."""

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.format is None:
            raise UnsupportedFormatError(
                "Config resources must use one of: .json, .toml, .yaml, .yml."
            )

    def load(self, *, default: object = MISSING) -> object:
        return self.read_data(default=default)

    def save(self, content: object, *, atomic: bool = True) -> Path:
        return self.write_data(content, atomic=atomic)

    def update(
        self,
        *mappings: Mapping[str, object],
        lock: bool = False,
        **changes: object,
    ) -> dict[str, object]:
        def apply_update() -> dict[str, object]:
            current = self.load(default={})
            if not isinstance(current, Mapping):
                raise TypeError("ConfigResource.update() requires a mapping-based document.")

            merged = dict(current)
            for mapping in mappings:
                merged.update(mapping)
            merged.update(changes)
            self.save(merged)
            return merged

        if lock:
            with self.lock():
                return apply_update()
        return apply_update()


class CacheResource(Resource):
    """Managed cache directory with file-oriented helpers."""

    def entry(
        self,
        *parts: str | Path,
        kind: ResourceKind | None = None,
        create: bool = False,
    ) -> Resource:
        return self.joinpath(*parts, kind=kind, create=create)

    def file(self, *parts: str | Path, create: bool = False) -> Resource:
        return self.entry(*parts, kind="file", create=create)

    def directory(self, *parts: str | Path, create: bool = False) -> "CacheResource":
        resource = self.joinpath(*parts, kind="directory", create=create, role="cache")
        if not isinstance(resource, CacheResource):  # pragma: no cover - defensive
            raise TypeError("Cache directory creation returned the wrong resource type.")
        return resource

    def remember(self, *parts: str | Path, content: object) -> Path:
        return self.file(*parts, create=True).write(content)

    def load(self, *parts: str | Path, default: object = MISSING) -> object:
        return self.file(*parts).content(default=default)

    def delete(self, *parts: str | Path, missing_ok: bool = True) -> None:
        target = self._resolve_child_path(*parts)

        if not target.exists():
            if missing_ok:
                return
            raise FileNotFoundError(target)

        if target.is_dir():
            shutil.rmtree(target)
        else:
            target.unlink()

    def clear(self) -> None:
        self.ensure()
        for child in list(self.path.iterdir()):
            self._assert_inside(child.resolve(strict=False))
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()


class AssetGroup(Resource):
    """Managed asset directory with convenience lookup helpers."""

    def file(self, *parts: str | Path, create: bool = False) -> Resource:
        return self.joinpath(*parts, kind="file", create=create)

    def directory(self, *parts: str | Path, create: bool = False) -> "AssetGroup":
        resource = self.joinpath(*parts, kind="directory", create=create, role="assets")
        if not isinstance(resource, AssetGroup):  # pragma: no cover - defensive
            raise TypeError("Asset directory creation returned the wrong resource type.")
        return resource

    def require(self, *parts: str | Path, kind: ResourceKind | None = None) -> Resource:
        resource = self.joinpath(*parts, kind=kind, create=False)
        if not resource.exists():
            raise FileNotFoundError(resource.path)
        return resource

    def files(self, pattern: str = "**/*") -> list[Path]:
        return [path for path in self.glob(pattern) if path.is_file()]


def create_resource(
    *,
    name: str,
    path: Path,
    kind: ResourceKind,
    create: bool = True,
    encoding: str = "utf-8",
    role: ResourceRole = "resource",
) -> Resource:
    resource_class: type[Resource]
    if role == "config":
        resource_class = ConfigResource
    elif role == "cache":
        resource_class = CacheResource
    elif role == "assets":
        resource_class = AssetGroup
    else:
        resource_class = Resource

    return resource_class(
        name=name,
        path=path,
        kind=kind,
        create=create,
        encoding=encoding,
        role=role,
    )
