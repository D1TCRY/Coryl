"""High-level resource manager for Python applications."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from .exceptions import (
    ManifestFormatError,
    ResourceConflictError,
    ResourceKindError,
    ResourceNotRegisteredError,
    UnsafePathError,
)
from .resources import MISSING, Resource, ResourceKind, ResourceSpec

ResourceInput = str | Path | ResourceSpec | Mapping[str, Any]


class ResourceManager:
    """Manage application files and directories relative to a root folder."""

    def __init__(
        self,
        root: str | Path,
        *,
        resources: Mapping[str, ResourceInput] | None = None,
        manifest_path: str | Path | None = None,
        create_missing: bool = True,
    ) -> None:
        self._root_path = Path(root).resolve(strict=False)
        self._manifest_path: Path | None = None
        self._manifest_data: dict[str, Any] | None = None
        self._manifest_resource_names: set[str] = set()
        self._create_missing = create_missing
        self._resources: dict[str, Resource] = {}

        if manifest_path is not None:
            self.load_manifest(manifest_path)

        if resources:
            self.register_many(resources, replace=True)

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}(root={self.root_path!r}, "
            f"resources={list(self._resources)!r}, manifest_path={self.manifest_path!r})"
        )

    def __str__(self) -> str:
        return (
            f"<{self.__class__.__name__} root='{self.root_path}' "
            f"resources={len(self._resources)}>"
        )

    def __getattr__(self, name: str) -> Path:
        if name.endswith("_file_path"):
            resource_name = name[: -len("_file_path")]
            try:
                return self.file(resource_name).path
            except (ResourceKindError, ResourceNotRegisteredError) as error:
                raise AttributeError(
                    f"{self.__class__.__name__!s} object has no attribute {name!r}"
                ) from error
        if name.endswith("_directory_path"):
            resource_name = name[: -len("_directory_path")]
            try:
                return self.directory(resource_name).path
            except (ResourceKindError, ResourceNotRegisteredError) as error:
                raise AttributeError(
                    f"{self.__class__.__name__!s} object has no attribute {name!r}"
                ) from error
        raise AttributeError(f"{self.__class__.__name__!s} object has no attribute {name!r}")

    @staticmethod
    def is_child_of(child: str | Path, parent: str | Path) -> bool:
        child_path = Path(child).resolve(strict=False)
        parent_path = Path(parent).resolve(strict=False)
        return child_path == parent_path or parent_path in child_path.parents

    @property
    def root_path(self) -> Path:
        return self._root_path

    @property
    def root_folder_path(self) -> Path:
        return self.root_path

    @property
    def manifest_path(self) -> Path | None:
        return self._manifest_path

    @property
    def config_file_path(self) -> Path:
        if self._manifest_path is not None:
            return self._manifest_path
        config_resource = self._resources.get("config")
        if config_resource is not None and config_resource.kind == "file":
            return config_resource.path
        raise AttributeError("No manifest_path has been configured.")

    @property
    def manifest(self) -> dict[str, Any] | None:
        return self._manifest_data

    @property
    def config(self) -> dict[str, Any]:
        if self._manifest_data is None:
            raise AttributeError("No manifest has been loaded.")
        return self._manifest_data

    @property
    def resources(self) -> dict[str, Resource]:
        return dict(self._resources)

    @property
    def file_paths(self) -> list[Path]:
        return [resource.path for resource in self._resources.values() if resource.kind == "file"]

    @property
    def directory_paths(self) -> list[Path]:
        return [resource.path for resource in self._resources.values() if resource.kind == "directory"]

    @property
    def paths(self) -> list[Path]:
        return self.file_paths + self.directory_paths

    def load_manifest(self, manifest_path: str | Path) -> dict[str, Any]:
        resolved_manifest_path = self._resolve_from_root(manifest_path)
        self._manifest_path = resolved_manifest_path

        raw_content = resolved_manifest_path.read_text(encoding="utf-8")
        try:
            self._manifest_data = json.loads(raw_content)
        except json.JSONDecodeError as error:
            raise ManifestFormatError(
                f"Manifest file '{resolved_manifest_path}' is not valid JSON."
            ) from error

        parsed_resources = self._parse_manifest(self._manifest_data)
        for stale_name in self._manifest_resource_names - set(parsed_resources):
            self._resources.pop(stale_name, None)

        for name, spec in parsed_resources.items():
            self.register(name, spec, replace=True)

        self._manifest_resource_names = set(parsed_resources)
        return self._manifest_data

    def load_config(self) -> dict[str, Any]:
        if self._manifest_path is None or self._manifest_data is None:
            raise AttributeError("No manifest has been loaded.")
        return self.load_manifest(self._manifest_path)

    def register(
        self,
        name: str,
        definition: ResourceInput,
        *,
        replace: bool = False,
    ) -> Resource:
        if not isinstance(name, str) or not name.strip():
            raise TypeError("Resource name must be a non-empty string.")
        if name in self._resources and not replace:
            raise ResourceConflictError(f"Resource '{name}' is already registered.")

        spec = self._coerce_resource_spec(definition)
        resolved_path = self._resolve_from_root(spec.relative_path)
        resource = Resource(
            name=name,
            path=resolved_path,
            kind=spec.kind,
            create=spec.create,
            encoding=spec.encoding,
        )
        self._resources[name] = resource
        return resource

    def register_file(
        self,
        name: str,
        relative_path: str | Path,
        *,
        create: bool | None = None,
        encoding: str = "utf-8",
        replace: bool = False,
    ) -> Resource:
        spec = ResourceSpec.file(
            relative_path,
            create=self._create_missing if create is None else create,
            encoding=encoding,
        )
        return self.register(name, spec, replace=replace)

    def register_directory(
        self,
        name: str,
        relative_path: str | Path,
        *,
        create: bool | None = None,
        replace: bool = False,
    ) -> Resource:
        spec = ResourceSpec.directory(
            relative_path,
            create=self._create_missing if create is None else create,
        )
        return self.register(name, spec, replace=replace)

    def register_many(
        self,
        resources: Mapping[str, ResourceInput],
        *,
        replace: bool = False,
    ) -> dict[str, Resource]:
        registered: dict[str, Resource] = {}
        for name, definition in resources.items():
            registered[name] = self.register(name, definition, replace=replace)
        return registered

    def resource(self, name: str) -> Resource:
        try:
            return self._resources[name]
        except KeyError as error:
            raise ResourceNotRegisteredError(f"Resource '{name}' is not registered.") from error

    def file(self, name: str) -> Resource:
        resource = self.resource(name)
        if resource.kind != "file":
            raise ResourceKindError(f"Resource '{name}' is a directory, not a file.")
        return resource

    def directory(self, name: str) -> Resource:
        resource = self.resource(name)
        if resource.kind != "directory":
            raise ResourceKindError(f"Resource '{name}' is a file, not a directory.")
        return resource

    def path(self, name: str) -> Path:
        return self.resource(name).path

    def content(self, name: str, default: Any = MISSING) -> Any:
        return self.resource(name).content(default=default)

    def write_content(self, name: str, content: Any) -> Path:
        return self.file(name).write(content)

    def ensure(self, name: str) -> Path:
        return self.resource(name).ensure()

    def resolve(self, *parts: str | Path) -> Path:
        return self._resolve_from_root(Path(*parts))

    def _resolve_from_root(self, relative_path: str | Path) -> Path:
        candidate = (self.root_path / Path(relative_path)).resolve(strict=False)
        if not self.is_child_of(candidate, self.root_path):
            raise UnsafePathError(
                f"Path '{candidate}' escapes the root folder '{self.root_path}'."
            )
        return candidate

    def _coerce_resource_spec(self, definition: ResourceInput) -> ResourceSpec:
        if isinstance(definition, ResourceSpec):
            return definition

        if isinstance(definition, (str, Path)):
            return self._infer_resource_spec(definition)

        if isinstance(definition, Mapping):
            try:
                path_value = definition["path"]
            except KeyError as error:
                raise ManifestFormatError("Resource mapping must contain a 'path' key.") from error

            kind = definition.get("kind")
            create = definition.get("create", self._create_missing)
            encoding = definition.get("encoding", "utf-8")
            if kind is None:
                kind = self._infer_kind(path_value)
            return ResourceSpec(
                relative_path=Path(path_value),
                kind=kind,
                create=bool(create),
                encoding=str(encoding),
            )

        raise TypeError(
            "Resource definition must be a path, a ResourceSpec, or a mapping with a 'path' key."
        )

    def _infer_resource_spec(self, path_value: str | Path) -> ResourceSpec:
        return ResourceSpec(
            relative_path=Path(path_value),
            kind=self._infer_kind(path_value),
            create=self._create_missing,
        )

    @staticmethod
    def _infer_kind(path_value: str | Path) -> ResourceKind:
        return "file" if Path(path_value).suffix else "directory"

    def _parse_manifest(self, manifest_data: Mapping[str, Any]) -> dict[str, ResourceSpec]:
        parsed: dict[str, ResourceSpec] = {}

        resources_section = manifest_data.get("resources")
        if resources_section is not None:
            if not isinstance(resources_section, Mapping):
                raise ManifestFormatError("'resources' must be a mapping.")
            for name, definition in resources_section.items():
                parsed[str(name)] = self._coerce_resource_spec(definition)

        paths_section = manifest_data.get("paths")
        if paths_section is not None:
            if not isinstance(paths_section, Mapping):
                raise ManifestFormatError("'paths' must be a mapping.")

            files_section = paths_section.get("files", {})
            directories_section = paths_section.get("directories", {})

            if not isinstance(files_section, Mapping):
                raise ManifestFormatError("'paths.files' must be a mapping.")
            if not isinstance(directories_section, Mapping):
                raise ManifestFormatError("'paths.directories' must be a mapping.")

            for name, relative_path in files_section.items():
                parsed[str(name)] = ResourceSpec.file(
                    relative_path,
                    create=self._create_missing,
                )
            for name, relative_path in directories_section.items():
                parsed[str(name)] = ResourceSpec.directory(
                    relative_path,
                    create=self._create_missing,
                )

        if not parsed:
            raise ManifestFormatError(
                "Manifest must contain either 'resources' or 'paths'."
            )

        return parsed


class Coryl(ResourceManager):
    """Brand-friendly alias for the main resource manager."""
