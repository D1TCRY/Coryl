"""High-level resource manager for Python applications."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Generic, TypeVar

from ._paths import is_within_root, resolve_managed_path
from .exceptions import (
    ManifestFormatError,
    ResourceConflictError,
    ResourceKindError,
    ResourceNotRegisteredError,
)
from .resources import (
    MISSING,
    AssetGroup,
    CacheResource,
    ConfigResource,
    Resource,
    ResourceKind,
    ResourceSpec,
    create_resource,
)
from .serialization import load_from_path

ResourceInput = str | Path | ResourceSpec | Mapping[str, object]
TResource = TypeVar("TResource", bound=Resource)


class _NamespaceBase(Generic[TResource]):
    """Common helpers for typed resource namespaces."""

    def __init__(self, manager: "ResourceManager") -> None:
        self._manager = manager

    def __contains__(self, name: str) -> bool:
        try:
            self.get(name)
        except (ResourceNotRegisteredError, ResourceKindError):
            return False
        return True

    def __getitem__(self, name: str) -> TResource:
        return self.get(name)

    def names(self) -> list[str]:
        raise NotImplementedError

    def all(self) -> dict[str, TResource]:
        raise NotImplementedError

    def get(self, name: str) -> TResource:
        raise NotImplementedError


class ConfigNamespace(_NamespaceBase[ConfigResource]):
    """Register and retrieve config resources."""

    def add(
        self,
        name: str,
        relative_path: str | Path,
        *,
        create: bool | None = None,
        encoding: str = "utf-8",
        replace: bool = False,
    ) -> ConfigResource:
        return self._manager.register_config(
            name,
            relative_path,
            create=create,
            encoding=encoding,
            replace=replace,
        )

    def get(self, name: str = "config") -> ConfigResource:
        return self._manager.config_resource(name)

    def all(self) -> dict[str, ConfigResource]:
        return {
            name: resource
            for name, resource in self._manager._resources.items()
            if isinstance(resource, ConfigResource)
        }

    def names(self) -> list[str]:
        return list(self.all())


class CacheNamespace(_NamespaceBase[CacheResource]):
    """Register and retrieve cache directories."""

    def add(
        self,
        name: str,
        relative_path: str | Path,
        *,
        create: bool | None = None,
        replace: bool = False,
    ) -> CacheResource:
        return self._manager.register_cache(
            name,
            relative_path,
            create=create,
            replace=replace,
        )

    def get(self, name: str) -> CacheResource:
        return self._manager.cache_resource(name)

    def all(self) -> dict[str, CacheResource]:
        return {
            name: resource
            for name, resource in self._manager._resources.items()
            if isinstance(resource, CacheResource)
        }

    def names(self) -> list[str]:
        return list(self.all())


class AssetNamespace(_NamespaceBase[AssetGroup]):
    """Register and retrieve asset directories."""

    def add(
        self,
        name: str,
        relative_path: str | Path,
        *,
        create: bool | None = None,
        replace: bool = False,
    ) -> AssetGroup:
        return self._manager.register_assets(
            name,
            relative_path,
            create=create,
            replace=replace,
        )

    def get(self, name: str) -> AssetGroup:
        return self._manager.asset_group(name)

    def all(self) -> dict[str, AssetGroup]:
        return {
            name: resource
            for name, resource in self._manager._resources.items()
            if isinstance(resource, AssetGroup)
        }

    def names(self) -> list[str]:
        return list(self.all())


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
        self._manifest_data: dict[str, object] | None = None
        self._manifest_resource_names: set[str] = set()
        self._create_missing = create_missing
        self._resources: dict[str, Resource] = {}
        self._configs = ConfigNamespace(self)
        self._caches = CacheNamespace(self)
        self._assets = AssetNamespace(self)

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
        return is_within_root(child, parent)

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
    def manifest(self) -> dict[str, object] | None:
        return self._manifest_data

    @property
    def config(self) -> dict[str, object]:
        if self._manifest_data is None:
            raise AttributeError("No manifest has been loaded.")
        return self._manifest_data

    @property
    def resources(self) -> dict[str, Resource]:
        return dict(self._resources)

    @property
    def configs(self) -> ConfigNamespace:
        return self._configs

    @property
    def caches(self) -> CacheNamespace:
        return self._caches

    @property
    def assets(self) -> AssetNamespace:
        return self._assets

    @property
    def file_paths(self) -> list[Path]:
        return [resource.path for resource in self._resources.values() if resource.kind == "file"]

    @property
    def directory_paths(self) -> list[Path]:
        return [resource.path for resource in self._resources.values() if resource.kind == "directory"]

    @property
    def paths(self) -> list[Path]:
        return self.file_paths + self.directory_paths

    def load_manifest(self, manifest_path: str | Path) -> dict[str, object]:
        resolved_manifest_path = self._resolve_from_root(
            manifest_path,
            allow_absolute=True,
        )
        self._manifest_path = resolved_manifest_path

        raw_content = resolved_manifest_path.read_text(encoding="utf-8")
        try:
            manifest_data = load_from_path(resolved_manifest_path, raw_content)
        except Exception as error:
            raise ManifestFormatError(
                f"Manifest file '{resolved_manifest_path}' could not be loaded."
            ) from error

        if not isinstance(manifest_data, Mapping):
            raise ManifestFormatError("Manifest content must be a mapping.")

        self._manifest_data = dict(manifest_data)
        parsed_resources = self._parse_manifest(self._manifest_data)
        for stale_name in self._manifest_resource_names - set(parsed_resources):
            self._resources.pop(stale_name, None)

        for name, spec in parsed_resources.items():
            self.register(name, spec, replace=True)

        self._manifest_resource_names = set(parsed_resources)
        return self._manifest_data

    def load_config(self) -> dict[str, object]:
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
        resource = create_resource(
            name=name,
            path=resolved_path,
            kind=spec.kind,
            create=spec.create,
            encoding=spec.encoding,
            role=spec.role,
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

    def register_config(
        self,
        name: str,
        relative_path: str | Path,
        *,
        create: bool | None = None,
        encoding: str = "utf-8",
        replace: bool = False,
    ) -> ConfigResource:
        self.register(
            name,
            ResourceSpec.config(
                relative_path,
                create=self._create_missing if create is None else create,
                encoding=encoding,
            ),
            replace=replace,
        )
        return self.config_resource(name)

    def register_cache(
        self,
        name: str,
        relative_path: str | Path,
        *,
        create: bool | None = None,
        replace: bool = False,
    ) -> CacheResource:
        self.register(
            name,
            ResourceSpec.cache(
                relative_path,
                create=self._create_missing if create is None else create,
            ),
            replace=replace,
        )
        return self.cache_resource(name)

    def register_assets(
        self,
        name: str,
        relative_path: str | Path,
        *,
        create: bool | None = None,
        replace: bool = False,
    ) -> AssetGroup:
        self.register(
            name,
            ResourceSpec.assets(
                relative_path,
                create=self._create_missing if create is None else create,
            ),
            replace=replace,
        )
        return self.asset_group(name)

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

    def config_resource(self, name: str = "config") -> ConfigResource:
        resource = self.resource(name)
        if not isinstance(resource, ConfigResource):
            raise ResourceKindError(f"Resource '{name}' is not a config resource.")
        return resource

    def cache_resource(self, name: str) -> CacheResource:
        resource = self.resource(name)
        if not isinstance(resource, CacheResource):
            raise ResourceKindError(f"Resource '{name}' is not a cache resource.")
        return resource

    def asset_group(self, name: str) -> AssetGroup:
        resource = self.resource(name)
        if not isinstance(resource, AssetGroup):
            raise ResourceKindError(f"Resource '{name}' is not an asset resource.")
        return resource

    def path(self, name: str) -> Path:
        return self.resource(name).path

    def content(self, name: str, default: object = MISSING) -> object:
        return self.resource(name).content(default=default)

    def write_content(self, name: str, content: object) -> Path:
        return self.file(name).write(content)

    def ensure(self, name: str) -> Path:
        return self.resource(name).ensure()

    def resolve(self, *parts: str | Path) -> Path:
        return self._resolve_from_root(Path(*parts))

    def _resolve_from_root(
        self,
        relative_path: str | Path,
        *,
        allow_absolute: bool = False,
    ) -> Path:
        return resolve_managed_path(
            relative_path,
            base_path=self.root_path,
            allowed_root=self.root_path,
            allow_absolute=allow_absolute,
        )

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

            if not isinstance(path_value, (str, Path)):
                raise ManifestFormatError("Resource mapping 'path' must be a string or Path.")

            kind = definition.get("kind")
            create = definition.get("create", self._create_missing)
            encoding = definition.get("encoding", "utf-8")
            role = definition.get("role", "resource")
            if kind is None:
                kind = self._infer_kind(path_value)
            return ResourceSpec(
                relative_path=Path(path_value),
                kind=kind,
                create=bool(create),
                encoding=str(encoding),
                role=str(role),
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

    def _parse_manifest(self, manifest_data: Mapping[str, object]) -> dict[str, ResourceSpec]:
        resources_section = manifest_data.get("resources")
        if resources_section is None:
            raise ManifestFormatError("Manifest must contain a top-level 'resources' mapping.")
        if not isinstance(resources_section, Mapping):
            raise ManifestFormatError("'resources' must be a mapping.")

        parsed: dict[str, ResourceSpec] = {}
        for name, definition in resources_section.items():
            parsed[str(name)] = self._coerce_resource_spec(definition)
        return parsed


class Coryl(ResourceManager):
    """Brand-friendly alias for the main resource manager."""
