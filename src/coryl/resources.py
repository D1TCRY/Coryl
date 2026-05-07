"""Resource models used by Coryl."""

from __future__ import annotations

import shutil
from collections.abc import Iterator, Mapping
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass
from importlib import resources as importlib_resources
from importlib.resources.abc import Traversable
from pathlib import Path, PurePosixPath
from typing import IO, Literal

from ._io import _atomic_write_bytes, _atomic_write_text
from ._locks import managed_lock
from ._paths import is_within_root, resolve_managed_path, validate_managed_path_input
from .exceptions import (
    CorylPathError,
    CorylReadOnlyResourceError,
    CorylValidationError,
    ResourceKindError,
    UnsafePathError,
    UnsupportedFormatError,
)
from .serialization import dump_to_path, load_from_path, structured_format_for_path

ResourceKind = Literal["file", "directory"]
ResourceRole = Literal["resource", "config", "cache", "assets", "data", "logs"]
MISSING = object()


@dataclass(frozen=True, slots=True)
class ResourceSpec:
    """Declarative description of a managed resource."""

    relative_path: Path
    kind: ResourceKind = "file"
    create: bool = True
    encoding: str = "utf-8"
    role: ResourceRole = "resource"
    readonly: bool = False
    required: bool = False
    format: str | None = None
    schema: str | None = None
    backend: str | None = None

    def __post_init__(self) -> None:
        relative_path = validate_managed_path_input(self.relative_path)
        if not isinstance(self.create, bool):
            raise CorylValidationError("ResourceSpec.create must be a boolean.")
        if not isinstance(self.readonly, bool):
            raise CorylValidationError("ResourceSpec.readonly must be a boolean.")
        if not isinstance(self.required, bool):
            raise CorylValidationError("ResourceSpec.required must be a boolean.")
        if not isinstance(self.encoding, str) or not self.encoding:
            raise CorylValidationError("ResourceSpec.encoding must be a non-empty string.")
        if self.kind not in {"file", "directory"}:
            raise ResourceKindError("ResourceSpec.kind must be either 'file' or 'directory'.")
        if self.role not in {"resource", "config", "cache", "assets", "data", "logs"}:
            raise CorylValidationError("ResourceSpec.role is invalid.")
        if self.format is not None and not isinstance(self.format, str):
            raise CorylValidationError("ResourceSpec.format must be a string when provided.")
        if self.schema is not None and not isinstance(self.schema, str):
            raise CorylValidationError("ResourceSpec.schema must be a string when provided.")
        if self.backend is not None and not isinstance(self.backend, str):
            raise CorylValidationError("ResourceSpec.backend must be a string when provided.")
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
        readonly: bool = False,
        required: bool = False,
        format: str | None = None,
        schema: str | None = None,
        backend: str | None = None,
    ) -> "ResourceSpec":
        return cls(
            relative_path=Path(path),
            kind="file",
            create=create,
            encoding=encoding,
            readonly=readonly,
            required=required,
            format=format,
            schema=schema,
            backend=backend,
        )

    @classmethod
    def directory(
        cls,
        path: str | Path,
        *,
        create: bool = True,
        encoding: str = "utf-8",
        readonly: bool = False,
        required: bool = False,
        format: str | None = None,
        schema: str | None = None,
        backend: str | None = None,
    ) -> "ResourceSpec":
        return cls(
            relative_path=Path(path),
            kind="directory",
            create=create,
            encoding=encoding,
            readonly=readonly,
            required=required,
            format=format,
            schema=schema,
            backend=backend,
        )

    @classmethod
    def config(
        cls,
        path: str | Path,
        *,
        create: bool = True,
        encoding: str = "utf-8",
        readonly: bool = False,
        required: bool = False,
        format: str | None = None,
        schema: str | None = None,
        backend: str | None = None,
    ) -> "ResourceSpec":
        return cls(
            relative_path=Path(path),
            kind="file",
            create=create,
            encoding=encoding,
            role="config",
            readonly=readonly,
            required=required,
            format=format,
            schema=schema,
            backend=backend,
        )

    @classmethod
    def cache(
        cls,
        path: str | Path,
        *,
        create: bool = True,
        encoding: str = "utf-8",
        readonly: bool = False,
        required: bool = False,
        format: str | None = None,
        schema: str | None = None,
        backend: str | None = None,
    ) -> "ResourceSpec":
        return cls(
            relative_path=Path(path),
            kind="directory",
            create=create,
            encoding=encoding,
            role="cache",
            readonly=readonly,
            required=required,
            format=format,
            schema=schema,
            backend=backend,
        )

    @classmethod
    def assets(
        cls,
        path: str | Path,
        *,
        create: bool = True,
        encoding: str = "utf-8",
        readonly: bool = False,
        required: bool = False,
        format: str | None = None,
        schema: str | None = None,
        backend: str | None = None,
    ) -> "ResourceSpec":
        return cls(
            relative_path=Path(path),
            kind="directory",
            create=create,
            encoding=encoding,
            role="assets",
            readonly=readonly,
            required=required,
            format=format,
            schema=schema,
            backend=backend,
        )

    @classmethod
    def data(
        cls,
        path: str | Path,
        *,
        create: bool = True,
        encoding: str = "utf-8",
        readonly: bool = False,
        required: bool = False,
        format: str | None = None,
        schema: str | None = None,
        backend: str | None = None,
    ) -> "ResourceSpec":
        return cls(
            relative_path=Path(path),
            kind="file" if Path(path).suffix else "directory",
            create=create,
            encoding=encoding,
            role="data",
            readonly=readonly,
            required=required,
            format=format,
            schema=schema,
            backend=backend,
        )

    @classmethod
    def logs(
        cls,
        path: str | Path,
        *,
        create: bool = True,
        encoding: str = "utf-8",
        readonly: bool = False,
        required: bool = False,
        format: str | None = None,
        schema: str | None = None,
        backend: str | None = None,
    ) -> "ResourceSpec":
        return cls(
            relative_path=Path(path),
            kind="file" if Path(path).suffix else "directory",
            create=create,
            encoding=encoding,
            role="logs",
            readonly=readonly,
            required=required,
            format=format,
            schema=schema,
            backend=backend,
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
    readonly: bool = False
    required: bool = False
    declared_format: str | None = None
    schema: str | None = None
    backend: str | None = None
    managed_root: Path | None = None
    root_name: str = "root"

    def __post_init__(self) -> None:
        self.path = self.path.resolve(strict=False)
        if not isinstance(self.create, bool):
            raise CorylValidationError("Resource.create must be a boolean.")
        if not isinstance(self.readonly, bool):
            raise CorylValidationError("Resource.readonly must be a boolean.")
        if not isinstance(self.required, bool):
            raise CorylValidationError("Resource.required must be a boolean.")
        if not isinstance(self.encoding, str) or not self.encoding:
            raise CorylValidationError("Resource.encoding must be a non-empty string.")
        if self.kind not in {"file", "directory"}:
            raise ResourceKindError("Resource.kind must be either 'file' or 'directory'.")
        if self.role not in {"resource", "config", "cache", "assets", "data", "logs"}:
            raise CorylValidationError("Resource.role is invalid.")
        if self.declared_format is not None and not isinstance(self.declared_format, str):
            raise CorylValidationError("Resource.declared_format must be a string when provided.")
        if self.schema is not None and not isinstance(self.schema, str):
            raise CorylValidationError("Resource.schema must be a string when provided.")
        if self.backend is not None and not isinstance(self.backend, str):
            raise CorylValidationError("Resource.backend must be a string when provided.")
        if self.managed_root is not None:
            self.managed_root = Path(self.managed_root).resolve(strict=False)
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
        if self.path.exists():
            return self.path
        self._assert_writable("created")
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
        mode = self._open_mode(args, kwargs)
        if self._mode_writes(mode):
            self._assert_writable("opened for writing")
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
        self._assert_writable("written")

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
        self._assert_writable("written")

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
        self._assert_writable("written")

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
            readonly=self.readonly,
            managed_root=self.path,
            root_name=self.root_name,
        )

    def iterdir(self) -> Iterator[Path]:
        if self.kind != "directory":
            raise ResourceKindError(f"Resource '{self.name}' is a file, not a directory.")
        if not self.readonly:
            self.ensure()
        return self.path.iterdir()

    def glob(self, pattern: str) -> list[Path]:
        if self.kind != "directory":
            raise ResourceKindError(f"Resource '{self.name}' is a file, not a directory.")
        if not self.readonly:
            self.ensure()
        return sorted(self.path.glob(pattern))

    @contextmanager
    def lock(self, timeout: float | None = None) -> Iterator["Resource"]:
        self._assert_writable("locked")
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

        self._assert_writable("written")
        payload = dump_to_path(self.path, content)
        return self.write_text(payload, encoding=encoding, atomic=atomic)

    def _assert_inside(self, candidate: Path) -> None:
        if not is_within_root(candidate, self.path):
            raise UnsafePathError("Joined path escapes the directory resource root.")

    def _assert_writable(self, operation: str) -> None:
        if self.readonly:
            raise CorylReadOnlyResourceError(
                f"Resource '{self.name}' is read-only and cannot be {operation}."
            )

    @staticmethod
    def _open_mode(args: tuple[object, ...], kwargs: Mapping[str, object]) -> str:
        if "mode" in kwargs and isinstance(kwargs["mode"], str):
            return kwargs["mode"]
        if args and isinstance(args[0], str):
            return args[0]
        return "r"

    @staticmethod
    def _mode_writes(mode: str) -> bool:
        return any(flag in mode for flag in ("w", "a", "x", "+"))

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


@dataclass(slots=True)
class LayeredConfigResource(ConfigResource):
    """Configuration resource with simple secrets-directory overrides."""

    secrets_dir: Path | None = None

    def __post_init__(self) -> None:
        ConfigResource.__post_init__(self)
        if self.secrets_dir is not None:
            self.secrets_dir = Path(self.secrets_dir).resolve(strict=False)

    def load(self, *, default: object = MISSING) -> object:
        base_document = self.load_base(default=default)
        secret_overrides = self._load_secret_overrides()
        if not secret_overrides:
            return base_document
        if not isinstance(base_document, Mapping):
            raise TypeError(
                "LayeredConfigResource.load() requires a mapping-based document when secrets_dir "
                "is used."
            )
        merged = dict(base_document)
        merged.update(secret_overrides)
        return merged

    def load_base(self, *, default: object = MISSING) -> object:
        return ConfigResource.load(self, default=default)

    def update(
        self,
        *mappings: Mapping[str, object],
        lock: bool = False,
        **changes: object,
    ) -> dict[str, object]:
        def apply_update() -> dict[str, object]:
            current = self.load_base(default={})
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

    def _load_secret_overrides(self) -> dict[str, str]:
        if self.secrets_dir is None:
            return {}
        if not self.secrets_dir.exists():
            return {}
        if not self.secrets_dir.is_dir():
            raise CorylValidationError("Layered config secrets_dir must point to a directory.")

        overrides: dict[str, str] = {}
        for candidate in sorted(self.secrets_dir.iterdir()):
            if candidate.is_file():
                overrides[candidate.name] = candidate.read_text(encoding=self.encoding)
        return overrides


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
        self._assert_writable("deleted")
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
        self._assert_writable("cleared")
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


@dataclass(slots=True)
class PackageAssetResource:
    """Read-only package asset file accessed through importlib.resources."""

    name: str
    package: str
    traversable: Traversable
    package_path: PurePosixPath
    relative_path: PurePosixPath
    kind: ResourceKind = "file"
    readonly: bool = True
    role: ResourceRole = "assets"
    encoding: str = "utf-8"

    def __str__(self) -> str:
        return self.display_path

    @property
    def display_path(self) -> str:
        relative = self.package_path.as_posix()
        if relative == ".":
            return f"package://{self.package}"
        return f"package://{self.package}/{relative}"

    @property
    def path(self) -> Path:
        raise CorylPathError(
            f"Package asset '{self.display_path}' does not have a stable filesystem path. "
            "Use as_file() to materialize a temporary path."
        )

    def exists(self) -> bool:
        return _traversable_exists(self.traversable)

    def is_file(self) -> bool:
        return self.traversable.is_file()

    def is_dir(self) -> bool:
        return self.traversable.is_dir()

    def open(self, *args: object, **kwargs: object) -> IO[str] | IO[bytes]:
        mode = Resource._open_mode(args, kwargs)
        if Resource._mode_writes(mode):
            self._assert_writable("opened for writing")
        self._assert_file_available()
        return self.traversable.open(*args, **kwargs)

    def read_text(self, *, encoding: str = "utf-8") -> str:
        self._assert_file_available()
        return self.traversable.read_text(encoding=encoding)

    def read_bytes(self) -> bytes:
        self._assert_file_available()
        return self.traversable.read_bytes()

    def write_text(
        self,
        content: str,
        *,
        encoding: str = "utf-8",
        atomic: bool = True,
    ) -> Path:
        del content, encoding, atomic
        self._assert_writable("written")
        raise AssertionError("unreachable")

    def write_bytes(self, content: bytes, *, atomic: bool = True) -> Path:
        del content, atomic
        self._assert_writable("written")
        raise AssertionError("unreachable")

    def write(self, content: object) -> Path:
        del content
        self._assert_writable("written")
        raise AssertionError("unreachable")

    def as_file(self) -> AbstractContextManager[Path]:
        self._assert_file_available()
        return importlib_resources.as_file(self.traversable)

    def _assert_file_available(self) -> None:
        if self.kind != "file" or self.traversable.is_dir():
            raise ResourceKindError(f"Resource '{self.name}' is a directory, not a file.")
        if not self.exists():
            raise FileNotFoundError(self.display_path)

    def _assert_writable(self, operation: str) -> None:
        raise CorylReadOnlyResourceError(
            f"Package asset '{self.name}' is read-only and cannot be {operation}."
        )


@dataclass(slots=True)
class PackageAssetGroup:
    """Read-only asset directory backed by importlib.resources."""

    name: str
    package: str
    traversable: Traversable
    package_path: PurePosixPath
    relative_path: PurePosixPath
    readonly: bool = True
    role: ResourceRole = "assets"
    kind: ResourceKind = "directory"
    encoding: str = "utf-8"

    def __str__(self) -> str:
        return self.display_path

    @property
    def display_path(self) -> str:
        relative = self.package_path.as_posix()
        if relative == ".":
            return f"package://{self.package}"
        return f"package://{self.package}/{relative}"

    @property
    def path(self) -> Path:
        raise CorylPathError(
            f"Package asset group '{self.display_path}' does not have a stable filesystem path. "
            "Use file(...).as_file() for individual files or copy_to() for directories."
        )

    def exists(self, *parts: str | Path) -> bool:
        candidate = self._resolve(*parts)
        return _traversable_exists(candidate)

    def file(self, *parts: str | Path, create: bool = False) -> PackageAssetResource:
        if create:
            raise CorylReadOnlyResourceError(
                f"Package asset group '{self.name}' is read-only and cannot create files."
            )
        package_path, relative_path, candidate = self._resolve_with_relative(*parts)
        child_name = _child_resource_name(self.name, relative_path)
        return PackageAssetResource(
            name=child_name,
            package=self.package,
            traversable=candidate,
            package_path=package_path,
            relative_path=relative_path,
            readonly=True,
            encoding=self.encoding,
        )

    def directory(self, *parts: str | Path, create: bool = False) -> "PackageAssetGroup":
        if create:
            raise CorylReadOnlyResourceError(
                f"Package asset group '{self.name}' is read-only and cannot create directories."
            )
        package_path, relative_path, candidate = self._resolve_with_relative(*parts)
        child_name = _child_resource_name(self.name, relative_path)
        return PackageAssetGroup(
            name=child_name,
            package=self.package,
            traversable=candidate,
            package_path=package_path,
            relative_path=relative_path,
            readonly=True,
            encoding=self.encoding,
        )

    def require(
        self,
        *parts: str | Path,
        kind: ResourceKind | None = None,
    ) -> PackageAssetResource | "PackageAssetGroup":
        package_path, relative_path, candidate = self._resolve_with_relative(*parts)
        child_name = _child_resource_name(self.name, relative_path)
        if not _traversable_exists(candidate):
            raise FileNotFoundError(_package_display_path(self.package, package_path))

        if kind == "file":
            if candidate.is_dir():
                raise ResourceKindError(f"Resource '{child_name}' is a directory, not a file.")
            return self.file(*parts)
        if kind == "directory":
            if not candidate.is_dir():
                raise ResourceKindError(f"Resource '{child_name}' is a file, not a directory.")
            return self.directory(*parts)
        if candidate.is_dir():
            return self.directory(*parts)
        return self.file(*parts)

    def read_text(self, *parts: str | Path, encoding: str = "utf-8") -> str:
        resource = self.require(*parts, kind="file")
        if not isinstance(resource, PackageAssetResource):  # pragma: no cover - defensive
            raise TypeError("Package asset read_text() resolved to a directory.")
        return resource.read_text(encoding=encoding)

    def read_bytes(self, *parts: str | Path) -> bytes:
        resource = self.require(*parts, kind="file")
        if not isinstance(resource, PackageAssetResource):  # pragma: no cover - defensive
            raise TypeError("Package asset read_bytes() resolved to a directory.")
        return resource.read_bytes()

    def as_file(self, *parts: str | Path) -> AbstractContextManager[Path]:
        if not parts:
            raise CorylPathError(
                f"Package asset group '{self.display_path}' cannot be exposed as a single path. "
                "Use file(...).as_file() for individual files or copy_to() for directories."
            )
        resource = self.require(*parts, kind="file")
        if not isinstance(resource, PackageAssetResource):  # pragma: no cover - defensive
            raise TypeError("Package asset as_file() resolved to a directory.")
        return resource.as_file()

    def files(self, pattern: str = "**/*") -> list[PackageAssetResource]:
        matches: list[PackageAssetResource] = []
        for relative_path, candidate in _iter_traversable_files(self.traversable, PurePosixPath(".")):
            if relative_path.match(pattern):
                matches.append(
                    PackageAssetResource(
                        name=_child_resource_name(self.name, relative_path),
                        package=self.package,
                        traversable=candidate,
                        package_path=_join_pure_posix(self.package_path, relative_path),
                        relative_path=relative_path,
                        readonly=True,
                        encoding=self.encoding,
                    )
                )
        return matches

    def copy_to(self, target_directory: str | Path, *, overwrite: bool = False) -> Path:
        destination_root = Path(target_directory).resolve(strict=False)
        if destination_root.exists() and not destination_root.is_dir():
            raise NotADirectoryError(destination_root)
        destination_root.mkdir(parents=True, exist_ok=True)

        for relative_path, candidate in _iter_traversable_files(self.traversable, PurePosixPath(".")):
            destination_path = destination_root.joinpath(*relative_path.parts)
            if destination_path.exists() and not overwrite:
                raise FileExistsError(destination_path)
            destination_path.parent.mkdir(parents=True, exist_ok=True)
            destination_path.write_bytes(candidate.read_bytes())

        return destination_root

    def _resolve(self, *parts: str | Path) -> Traversable:
        return self._resolve_with_relative(*parts)[2]

    def _resolve_with_relative(
        self,
        *parts: str | Path,
    ) -> tuple[PurePosixPath, PurePosixPath, Traversable]:
        normalized_parts = _normalize_package_parts(*parts)
        package_path = self.package_path
        relative_path = self.relative_path
        candidate = self.traversable
        for part in normalized_parts:
            package_path = package_path / part
            relative_path = relative_path / part
            candidate = candidate.joinpath(part)
        return package_path, relative_path, candidate


def _normalize_package_parts(*parts: str | Path) -> tuple[str, ...]:
    if not parts:
        return ()

    raw_path = validate_managed_path_input(Path(*parts))
    return tuple(part for part in raw_path.parts if part not in {"."})


def _traversable_exists(candidate: Traversable) -> bool:
    return candidate.is_file() or candidate.is_dir()


def _package_display_path(package: str, relative_path: PurePosixPath) -> str:
    relative = relative_path.as_posix()
    if relative == ".":
        return f"package://{package}"
    return f"package://{package}/{relative}"


def _child_resource_name(root_name: str, relative_path: PurePosixPath) -> str:
    relative = relative_path.as_posix()
    if relative == ".":
        return root_name
    return f"{root_name}/{relative}"


def _join_pure_posix(base_path: PurePosixPath, relative_path: PurePosixPath) -> PurePosixPath:
    if relative_path == PurePosixPath("."):
        return base_path
    return base_path / relative_path


def _iter_traversable_files(
    root: Traversable,
    base_relative_path: PurePosixPath,
) -> Iterator[tuple[PurePosixPath, Traversable]]:
    for child in sorted(root.iterdir(), key=lambda candidate: candidate.name):
        child_relative_path = (
            PurePosixPath(child.name)
            if base_relative_path == PurePosixPath(".")
            else base_relative_path / child.name
        )
        if child.is_dir():
            yield from _iter_traversable_files(child, child_relative_path)
            continue
        yield child_relative_path, child


def create_resource(
    *,
    name: str,
    path: Path,
    kind: ResourceKind,
    create: bool = True,
    encoding: str = "utf-8",
    role: ResourceRole = "resource",
    readonly: bool = False,
    required: bool = False,
    declared_format: str | None = None,
    schema: str | None = None,
    backend: str | None = None,
    managed_root: Path | None = None,
    root_name: str = "root",
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
        readonly=readonly,
        required=required,
        declared_format=declared_format,
        schema=schema,
        backend=backend,
        managed_root=managed_root,
        root_name=root_name,
    )
