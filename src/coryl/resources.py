"""Resource models used by Coryl."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Literal

from .exceptions import ResourceKindError, UnsafePathError

ResourceKind = Literal["file", "directory"]
MISSING = object()


@dataclass(frozen=True, slots=True)
class ResourceSpec:
    """Declarative description of a managed resource."""

    relative_path: Path
    kind: ResourceKind = "file"
    create: bool = True
    encoding: str = "utf-8"

    def __post_init__(self) -> None:
        relative_path = Path(self.relative_path)
        if relative_path.is_absolute():
            raise ValueError("ResourceSpec.relative_path must be relative to the manager root.")
        if self.kind not in {"file", "directory"}:
            raise ValueError("ResourceSpec.kind must be either 'file' or 'directory'.")
        object.__setattr__(self, "relative_path", relative_path)

    @classmethod
    def file(
        cls,
        path: str | Path,
        *,
        create: bool = True,
        encoding: str = "utf-8",
    ) -> "ResourceSpec":
        return cls(relative_path=Path(path), kind="file", create=create, encoding=encoding)

    @classmethod
    def directory(
        cls,
        path: str | Path,
        *,
        create: bool = True,
        encoding: str = "utf-8",
    ) -> "ResourceSpec":
        return cls(relative_path=Path(path), kind="directory", create=create, encoding=encoding)


@dataclass(slots=True)
class Resource:
    """Concrete resource bound to a resolved path."""

    name: str
    path: Path
    kind: ResourceKind
    create: bool = True
    encoding: str = "utf-8"

    def __post_init__(self) -> None:
        self.path = self.path.resolve(strict=False)
        if self.kind not in {"file", "directory"}:
            raise ValueError("Resource.kind must be either 'file' or 'directory'.")
        if self.create:
            self.ensure()

    def __fspath__(self) -> str:
        return str(self.path)

    def __str__(self) -> str:
        return str(self.path)

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

    def open(self, *args: Any, **kwargs: Any):
        if self.kind != "file":
            raise ResourceKindError(f"Resource '{self.name}' is a directory, not a file.")
        return self.path.open(*args, **kwargs)

    def read_text(self, *, encoding: str | None = None) -> str:
        if self.kind != "file":
            raise ResourceKindError(f"Resource '{self.name}' is a directory, not a file.")
        return self.path.read_text(encoding=encoding or self.encoding)

    def write_text(self, content: str, *, encoding: str | None = None) -> Path:
        if self.kind != "file":
            raise ResourceKindError(f"Resource '{self.name}' is a directory, not a file.")
        self.ensure()
        self.path.write_text(content, encoding=encoding or self.encoding)
        return self.path

    def read_bytes(self) -> bytes:
        if self.kind != "file":
            raise ResourceKindError(f"Resource '{self.name}' is a directory, not a file.")
        return self.path.read_bytes()

    def write_bytes(self, content: bytes) -> Path:
        if self.kind != "file":
            raise ResourceKindError(f"Resource '{self.name}' is a directory, not a file.")
        self.ensure()
        self.path.write_bytes(content)
        return self.path

    def read_json(self, *, default: Any = MISSING, encoding: str | None = None) -> Any:
        if self.kind != "file":
            raise ResourceKindError(f"Resource '{self.name}' is a directory, not a file.")

        try:
            raw_content = self.read_text(encoding=encoding)
            if not raw_content.strip():
                if default is not MISSING:
                    return default
                return {}
            return json.loads(raw_content)
        except Exception:
            if default is not MISSING:
                return default
            raise

    def write_json(
        self,
        content: Any,
        *,
        indent: int = 4,
        ensure_ascii: bool = False,
        encoding: str | None = None,
    ) -> Path:
        if self.kind != "file":
            raise ResourceKindError(f"Resource '{self.name}' is a directory, not a file.")
        payload = json.dumps(content, indent=indent, ensure_ascii=ensure_ascii)
        return self.write_text(payload, encoding=encoding)

    def content(self, *, default: Any = MISSING) -> Any:
        try:
            return self._auto_read()
        except Exception:
            if default is not MISSING:
                return default
            raise

    def write(self, content: Any) -> Path:
        if self.kind != "file":
            raise ResourceKindError(f"Resource '{self.name}' is a directory, not a file.")

        if self.path.suffix.lower() == ".json":
            return self.write_json(content)
        if isinstance(content, bytes):
            return self.write_bytes(content)
        return self.write_text(str(content))

    def joinpath(
        self,
        *parts: str | Path,
        kind: ResourceKind | None = None,
        create: bool = False,
    ) -> "Resource":
        if self.kind != "directory":
            raise ResourceKindError(f"Resource '{self.name}' is a file, not a directory.")

        candidate = self.path.joinpath(*parts).resolve(strict=False)
        if candidate != self.path and self.path not in candidate.parents:
            raise UnsafePathError("Joined path escapes the directory resource root.")

        inferred_kind: ResourceKind = kind or ("file" if candidate.suffix else "directory")
        child_name = "/".join([self.name, *[str(part) for part in parts]])
        return Resource(
            name=child_name,
            path=candidate,
            kind=inferred_kind,
            create=create,
            encoding=self.encoding,
        )

    def iterdir(self) -> Iterable[Path]:
        if self.kind != "directory":
            raise ResourceKindError(f"Resource '{self.name}' is a file, not a directory.")
        self.ensure()
        return self.path.iterdir()

    def _auto_read(self) -> Any:
        suffix = self.path.suffix.lower()
        if suffix == ".json":
            return self.read_json()
        return self.read_text()

