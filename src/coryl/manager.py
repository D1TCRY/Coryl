"""High-level resource manager for Python applications."""

from __future__ import annotations

from importlib import import_module, resources as importlib_resources
from collections.abc import Mapping, Sequence
from importlib.resources.abc import Traversable
from pathlib import Path, PurePosixPath
from typing import Generic, TypeVar

from ._paths import is_within_root, resolve_managed_path, validate_managed_path_input
from .exceptions import (
    CorylOptionalDependencyError,
    CorylValidationError,
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
    DiskCacheResource,
    LayeredConfigResource,
    PackageAssetGroup,
    Resource,
    ResourceKind,
    ResourceSpec,
    create_resource,
)
from .serialization import load_from_path

ResourceInput = str | Path | ResourceSpec | Mapping[str, object]
AssetResource = AssetGroup | PackageAssetGroup
ManagedResource = Resource | PackageAssetGroup
TResource = TypeVar("TResource", bound=ManagedResource)
MANIFEST_VERSION = 2
DEFAULT_ROOT_NAME = "root"
CONFIG_ROOT_NAME = "config_root"
CACHE_ROOT_NAME = "cache_root"
DATA_ROOT_NAME = "data_root"
LOG_ROOT_NAME = "log_root"


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
        readonly: bool = False,
        version: int | None = None,
        schema: type[object] | None = None,
        replace: bool = False,
    ) -> ConfigResource:
        return self._manager.register_config(
            name,
            relative_path,
            create=create,
            encoding=encoding,
            readonly=readonly,
            version=version,
            schema=schema,
            replace=replace,
        )

    def layered(
        self,
        name: str,
        relative_path: str | Path | None = None,
        *,
        files: Sequence[str | Path] | None = None,
        create: bool | None = None,
        encoding: str = "utf-8",
        readonly: bool = False,
        env_prefix: str | None = None,
        secrets: str | Path | None = None,
        required: bool = False,
        secrets_dir: str | Path | None = None,
        version: int | None = None,
        schema: type[object] | None = None,
        replace: bool = False,
    ) -> LayeredConfigResource:
        return self._manager.register_layered_config(
            name,
            relative_path,
            files=files,
            create=create,
            encoding=encoding,
            readonly=readonly,
            env_prefix=env_prefix,
            secrets=secrets,
            required=required,
            secrets_dir=secrets_dir,
            version=version,
            schema=schema,
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
        readonly: bool = False,
        backend: str | None = None,
        replace: bool = False,
    ) -> CacheResource:
        return self._manager.register_cache(
            name,
            relative_path,
            create=create,
            readonly=readonly,
            backend=backend,
            replace=replace,
        )

    def diskcache(
        self,
        name: str,
        relative_path: str | Path,
        *,
        create: bool | None = None,
        readonly: bool = False,
        replace: bool = False,
    ) -> DiskCacheResource:
        resource = self._manager.register_cache(
            name,
            relative_path,
            create=create,
            readonly=readonly,
            backend="diskcache",
            replace=replace,
        )
        if not isinstance(resource, DiskCacheResource):  # pragma: no cover - defensive
            raise TypeError("DiskCache cache registration returned the wrong resource type.")
        return resource

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


class AssetNamespace(_NamespaceBase[AssetResource]):
    """Register and retrieve asset directories."""

    def add(
        self,
        name: str,
        relative_path: str | Path,
        *,
        create: bool | None = None,
        readonly: bool = False,
        replace: bool = False,
    ) -> AssetGroup:
        return self._manager.register_assets(
            name,
            relative_path,
            create=create,
            readonly=readonly,
            replace=replace,
        )

    def package(
        self,
        name: str,
        package: str,
        relative_path: str | Path = ".",
        *,
        readonly: bool = True,
        replace: bool = False,
    ) -> PackageAssetGroup:
        return self._manager.register_package_assets(
            name,
            package,
            relative_path,
            readonly=readonly,
            replace=replace,
        )

    def from_package(
        self,
        name: str,
        package: str,
        path: str | Path = "",
        *,
        replace: bool = False,
    ) -> PackageAssetGroup:
        return self._manager.register_package_assets(
            name,
            package,
            path,
            replace=replace,
        )

    def get(self, name: str) -> AssetResource:
        return self._manager.asset_group(name)

    def all(self) -> dict[str, AssetResource]:
        return {
            name: resource
            for name, resource in self._manager._resources.items()
            if isinstance(resource, (AssetGroup, PackageAssetGroup))
        }

    def names(self) -> list[str]:
        return list(self.all())


class DataNamespace(_NamespaceBase[Resource]):
    """Register and retrieve application data resources."""

    def add(
        self,
        name: str,
        relative_path: str | Path,
        *,
        create: bool | None = None,
        encoding: str = "utf-8",
        readonly: bool = False,
        replace: bool = False,
    ) -> Resource:
        return self._manager.register_data(
            name,
            relative_path,
            create=create,
            encoding=encoding,
            readonly=readonly,
            replace=replace,
        )

    def get(self, name: str) -> Resource:
        return self._manager.data_resource(name)

    def all(self) -> dict[str, Resource]:
        return {
            name: resource
            for name, resource in self._manager._resources.items()
            if resource.role == "data"
        }

    def names(self) -> list[str]:
        return list(self.all())


class LogNamespace(_NamespaceBase[Resource]):
    """Register and retrieve application log resources."""

    def add(
        self,
        name: str,
        relative_path: str | Path,
        *,
        create: bool | None = None,
        encoding: str = "utf-8",
        readonly: bool = False,
        replace: bool = False,
    ) -> Resource:
        return self._manager.register_log(
            name,
            relative_path,
            create=create,
            encoding=encoding,
            readonly=readonly,
            replace=replace,
        )

    def get(self, name: str) -> Resource:
        return self._manager.log_resource(name)

    def all(self) -> dict[str, Resource]:
        return {
            name: resource
            for name, resource in self._manager._resources.items()
            if resource.role == "logs"
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
        _named_roots: Mapping[str, str | Path] | None = None,
    ) -> None:
        base_root = Path(root).resolve(strict=False)
        self._root_paths = self._build_root_paths(base_root, _named_roots)
        self._root_path = self._root_paths[DEFAULT_ROOT_NAME]
        self._manifest_path: Path | None = None
        self._manifest_data: dict[str, object] | None = None
        self._manifest_resource_names: set[str] = set()
        self._create_missing = create_missing
        self._resources: dict[str, ManagedResource] = {}
        self._configs = ConfigNamespace(self)
        self._caches = CacheNamespace(self)
        self._assets = AssetNamespace(self)
        self._data = DataNamespace(self)
        self._logs = LogNamespace(self)

        if manifest_path is not None:
            self.load_manifest(manifest_path)

        if resources:
            self.register_many(resources, replace=True)

    @classmethod
    def for_app(
        cls,
        app_name: str,
        app_author: str | None = None,
        version: str | None = None,
        roaming: bool = False,
        multipath: bool = False,
        ensure: bool = True,
        create_missing: bool = True,
    ) -> "ResourceManager":
        if not isinstance(app_name, str) or not app_name.strip():
            raise TypeError("app_name must be a non-empty string.")
        if app_author is not None and (not isinstance(app_author, str) or not app_author.strip()):
            raise TypeError("app_author must be a non-empty string when provided.")
        if version is not None and (not isinstance(version, str) or not version.strip()):
            raise TypeError("version must be a non-empty string when provided.")

        try:
            platformdirs = import_module("platformdirs")
        except ModuleNotFoundError as error:
            raise CorylOptionalDependencyError(
                "Coryl.for_app() requires the optional 'platformdirs' dependency. "
                "Install it with 'pip install coryl[platform]'."
            ) from error

        platform = platformdirs.PlatformDirs(
            appname=app_name,
            appauthor=app_author,
            version=version,
            roaming=roaming,
            multipath=multipath,
            ensure_exists=ensure,
        )
        data_root = Path(platform.user_data_path).resolve(strict=False)
        named_roots = {
            DEFAULT_ROOT_NAME: data_root,
            CONFIG_ROOT_NAME: Path(platform.user_config_path).resolve(strict=False),
            CACHE_ROOT_NAME: Path(platform.user_cache_path).resolve(strict=False),
            DATA_ROOT_NAME: data_root,
            LOG_ROOT_NAME: Path(platform.user_log_path).resolve(strict=False),
        }
        return cls(
            data_root,
            create_missing=create_missing,
            _named_roots=named_roots,
        )

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
    def config_root_path(self) -> Path:
        return self._root_path_for(CONFIG_ROOT_NAME)

    @property
    def cache_root_path(self) -> Path:
        return self._root_path_for(CACHE_ROOT_NAME)

    @property
    def data_root_path(self) -> Path:
        return self._root_path_for(DATA_ROOT_NAME)

    @property
    def log_root_path(self) -> Path:
        return self._root_path_for(LOG_ROOT_NAME)

    @property
    def named_roots(self) -> dict[str, Path]:
        return dict(self._root_paths)

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
    def resources(self) -> dict[str, ManagedResource]:
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
    def data(self) -> DataNamespace:
        return self._data

    @property
    def logs(self) -> LogNamespace:
        return self._logs

    @property
    def file_paths(self) -> list[Path]:
        return [
            resource.path
            for resource in self._resources.values()
            if isinstance(resource, Resource) and resource.kind == "file"
        ]

    @property
    def directory_paths(self) -> list[Path]:
        return [
            resource.path
            for resource in self._resources.values()
            if isinstance(resource, Resource) and resource.kind == "directory"
        ]

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
            manifest_data = load_from_path(
                resolved_manifest_path,
                raw_content,
                unique_keys=True,
            )
        except Exception as error:
            raise ManifestFormatError(
                f"Manifest file '{resolved_manifest_path}' could not be loaded: {error}"
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
        spec = self._coerce_resource_spec(definition)
        return self._register_spec(name, spec, replace=replace)

    def register_file(
        self,
        name: str,
        relative_path: str | Path,
        *,
        create: bool | None = None,
        encoding: str = "utf-8",
        readonly: bool = False,
        replace: bool = False,
    ) -> Resource:
        spec = ResourceSpec.file(
            relative_path,
            create=self._default_create_value(create, readonly=readonly),
            encoding=encoding,
            readonly=readonly,
        )
        return self._register_spec(name, spec, replace=replace, root_name=DEFAULT_ROOT_NAME)

    def register_directory(
        self,
        name: str,
        relative_path: str | Path,
        *,
        create: bool | None = None,
        readonly: bool = False,
        replace: bool = False,
    ) -> Resource:
        spec = ResourceSpec.directory(
            relative_path,
            create=self._default_create_value(create, readonly=readonly),
            readonly=readonly,
        )
        return self._register_spec(name, spec, replace=replace, root_name=DEFAULT_ROOT_NAME)

    def register_config(
        self,
        name: str,
        relative_path: str | Path,
        *,
        create: bool | None = None,
        encoding: str = "utf-8",
        readonly: bool = False,
        version: int | None = None,
        schema: type[object] | None = None,
        replace: bool = False,
    ) -> ConfigResource:
        self._register_spec(
            name,
            ResourceSpec.config(
                relative_path,
                create=self._default_create_value(create, readonly=readonly),
                encoding=encoding,
                readonly=readonly,
            ),
            replace=replace,
            version=version,
            typed_schema=schema,
        )
        return self.config_resource(name)

    def register_layered_config(
        self,
        name: str,
        relative_path: str | Path | None = None,
        *,
        files: Sequence[str | Path] | None = None,
        create: bool | None = None,
        encoding: str = "utf-8",
        readonly: bool = False,
        env_prefix: str | None = None,
        secrets: str | Path | None = None,
        required: bool = False,
        secrets_dir: str | Path | None = None,
        version: int | None = None,
        schema: type[object] | None = None,
        replace: bool = False,
    ) -> LayeredConfigResource:
        self._validate_resource_name(name)
        self._ensure_replaceable(name, replace=replace)
        if secrets is not None and secrets_dir is not None:
            raise TypeError(
                "register_layered_config() accepts either 'secrets' or 'secrets_dir', not both."
            )

        layer_relative_paths = self._normalize_layered_relative_paths(relative_path, files=files)
        primary_relative_path = layer_relative_paths[-1]
        spec = ResourceSpec.config(
            primary_relative_path,
            create=self._default_create_value(create, readonly=readonly),
            encoding=encoding,
            readonly=readonly,
            required=required,
        )
        root_name = CONFIG_ROOT_NAME
        resolved_layer_paths = tuple(
            self._resolve_from_named_root(layer_path, root_name=root_name)
            for layer_path in layer_relative_paths
        )
        resolved_path = resolved_layer_paths[-1]
        resource = LayeredConfigResource(
            name=name,
            path=resolved_path,
            kind=spec.kind,
            create=spec.create,
            encoding=spec.encoding,
            role=spec.role,
            readonly=spec.readonly,
            required=spec.required,
            declared_format=spec.format,
            schema=spec.schema,
            backend=spec.backend,
            typed_schema=schema,
            version=version,
            managed_root=self._root_path_for(root_name),
            root_name=root_name,
            layer_paths=resolved_layer_paths,
            env_prefix=env_prefix,
            secrets_path=self._resolve_optional_rooted_path(secrets, root_name=root_name),
            secrets_dir=self._resolve_secrets_dir(secrets_dir, root_name=root_name),
        )
        self._resources[name] = resource
        return resource

    def register_cache(
        self,
        name: str,
        relative_path: str | Path,
        *,
        create: bool | None = None,
        readonly: bool = False,
        backend: str | None = None,
        replace: bool = False,
    ) -> CacheResource:
        self.register(
            name,
            ResourceSpec.cache(
                relative_path,
                create=self._default_create_value(create, readonly=readonly),
                readonly=readonly,
                backend=backend,
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
        readonly: bool = False,
        replace: bool = False,
    ) -> AssetGroup:
        self.register(
            name,
            ResourceSpec.assets(
                relative_path,
                create=self._default_create_value(create, readonly=readonly),
                readonly=readonly,
            ),
            replace=replace,
        )
        return self.asset_group(name)

    def register_data(
        self,
        name: str,
        relative_path: str | Path,
        *,
        create: bool | None = None,
        encoding: str = "utf-8",
        readonly: bool = False,
        replace: bool = False,
    ) -> Resource:
        self._register_spec(
            name,
            ResourceSpec.data(
                relative_path,
                create=self._default_create_value(create, readonly=readonly),
                encoding=encoding,
                readonly=readonly,
            ),
            replace=replace,
            root_name=DATA_ROOT_NAME,
        )
        return self.data_resource(name)

    def register_log(
        self,
        name: str,
        relative_path: str | Path,
        *,
        create: bool | None = None,
        encoding: str = "utf-8",
        readonly: bool = False,
        replace: bool = False,
    ) -> Resource:
        self._register_spec(
            name,
            ResourceSpec.logs(
                relative_path,
                create=self._default_create_value(create, readonly=readonly),
                encoding=encoding,
                readonly=readonly,
            ),
            replace=replace,
            root_name=LOG_ROOT_NAME,
        )
        return self.log_resource(name)

    def register_package_assets(
        self,
        name: str,
        package: str,
        relative_path: str | Path = ".",
        *,
        readonly: bool = True,
        replace: bool = False,
    ) -> PackageAssetGroup:
        self._validate_resource_name(name)
        if not isinstance(package, str) or not package.strip():
            raise TypeError("Package name must be a non-empty string.")
        self._ensure_replaceable(name, replace=replace)

        root_traversable = self._resolve_package_assets(package, relative_path)
        resource = PackageAssetGroup(
            name=name,
            package=package,
            traversable=root_traversable,
            package_path=PurePosixPath(self._package_relative_path(relative_path).as_posix()),
            relative_path=PurePosixPath("."),
            readonly=True,
        )
        self._resources[name] = resource
        return resource

    def register_many(
        self,
        resources: Mapping[str, ResourceInput],
        *,
        replace: bool = False,
    ) -> dict[str, ManagedResource]:
        registered: dict[str, ManagedResource] = {}
        for name, definition in resources.items():
            registered[name] = self.register(name, definition, replace=replace)
        return registered

    def resource(self, name: str) -> ManagedResource:
        try:
            return self._resources[name]
        except KeyError as error:
            raise ResourceNotRegisteredError(f"Resource '{name}' is not registered.") from error

    def file(self, name: str) -> Resource:
        resource = self.resource(name)
        if not isinstance(resource, Resource) or resource.kind != "file":
            raise ResourceKindError(f"Resource '{name}' is a directory, not a file.")
        return resource

    def directory(self, name: str) -> ManagedResource:
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

    def asset_group(self, name: str) -> AssetResource:
        resource = self.resource(name)
        if not isinstance(resource, (AssetGroup, PackageAssetGroup)):
            raise ResourceKindError(f"Resource '{name}' is not an asset resource.")
        return resource

    def data_resource(self, name: str) -> Resource:
        resource = self.resource(name)
        if resource.role != "data":
            raise ResourceKindError(f"Resource '{name}' is not a data resource.")
        return resource

    def log_resource(self, name: str) -> Resource:
        resource = self.resource(name)
        if resource.role != "logs":
            raise ResourceKindError(f"Resource '{name}' is not a log resource.")
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

    def audit_paths(self) -> dict[str, object]:
        resources: dict[str, dict[str, object]] = {}
        for name, resource in self._resources.items():
            if isinstance(resource, PackageAssetGroup):
                resources[name] = {
                    "path": resource.display_path,
                    "exists": resource.exists(),
                    "kind": resource.kind,
                    "role": resource.role,
                    "safe": True,
                }
                continue

            managed_root = resource.managed_root or self.root_path
            resources[name] = {
                "path": str(resource.path),
                "exists": resource.exists(),
                "kind": resource.kind,
                "role": resource.role,
                "safe": is_within_root(resource.path, managed_root),
            }

        return {
            "root": str(self.root_path),
            "resources": resources,
        }

    def _resolve_from_root(
        self,
        relative_path: str | Path,
        *,
        allow_absolute: bool = False,
    ) -> Path:
        return self._resolve_from_named_root(
            relative_path,
            root_name=DEFAULT_ROOT_NAME,
            allow_absolute=allow_absolute,
        )

    def _resolve_from_named_root(
        self,
        relative_path: str | Path,
        *,
        root_name: str,
        allow_absolute: bool = False,
    ) -> Path:
        root_path = self._root_path_for(root_name)
        return resolve_managed_path(
            relative_path,
            base_path=root_path,
            allowed_root=root_path,
            allow_absolute=allow_absolute,
        )

    def _register_spec(
        self,
        name: str,
        spec: ResourceSpec,
        *,
        replace: bool = False,
        root_name: str | None = None,
        version: int | None = None,
        typed_schema: type[object] | None = None,
    ) -> Resource:
        self._validate_resource_name(name)
        self._ensure_replaceable(name, replace=replace)

        actual_root_name = root_name or self._root_name_for_role(spec.role)
        managed_root = self._root_path_for(actual_root_name)
        resolved_path = self._resolve_from_named_root(
            spec.relative_path,
            root_name=actual_root_name,
        )
        resource = create_resource(
            name=name,
            path=resolved_path,
            kind=spec.kind,
            create=spec.create,
            encoding=spec.encoding,
            role=spec.role,
            readonly=spec.readonly,
            required=spec.required,
            declared_format=spec.format,
            schema=spec.schema,
            backend=spec.backend,
            typed_schema=typed_schema,
            version=version,
            managed_root=managed_root,
            root_name=actual_root_name,
        )
        self._resources[name] = resource
        return resource

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
            if kind is not None and not isinstance(kind, str):
                raise ManifestFormatError("Resource mapping 'kind' must be a string.")
            encoding = self._coerce_string_field(
                definition.get("encoding", "utf-8"),
                field_name="encoding",
            )
            role = self._coerce_string_field(
                definition.get("role", "resource"),
                field_name="role",
            )
            readonly = self._coerce_bool_field(
                definition.get("readonly", False),
                field_name="readonly",
            )
            create = self._coerce_bool_field(
                definition["create"],
                field_name="create",
            ) if "create" in definition else self._default_create_value(None, readonly=readonly)
            required = self._coerce_bool_field(
                definition.get("required", False),
                field_name="required",
            )
            format_name = self._coerce_optional_string_field(
                definition.get("format"),
                field_name="format",
            )
            schema_name = self._coerce_optional_string_field(
                definition.get("schema"),
                field_name="schema",
            )
            backend = self._coerce_optional_string_field(
                definition.get("backend"),
                field_name="backend",
            )
            if kind is None:
                kind = self._infer_kind(path_value)
            return ResourceSpec(
                relative_path=Path(path_value),
                kind=kind,
                create=create,
                encoding=encoding,
                role=role,
                readonly=readonly,
                required=required,
                format=format_name,
                schema=schema_name,
                backend=backend,
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

    def _default_create_value(self, create: bool | None, *, readonly: bool) -> bool:
        if create is not None:
            return create
        if readonly:
            return False
        return self._create_missing

    @staticmethod
    def _build_root_paths(
        base_root: Path,
        named_roots: Mapping[str, str | Path] | None,
    ) -> dict[str, Path]:
        roots = {
            DEFAULT_ROOT_NAME: base_root.resolve(strict=False),
            CONFIG_ROOT_NAME: base_root.resolve(strict=False),
            CACHE_ROOT_NAME: base_root.resolve(strict=False),
            DATA_ROOT_NAME: base_root.resolve(strict=False),
            LOG_ROOT_NAME: base_root.resolve(strict=False),
        }
        if named_roots is None:
            return roots

        for name, path_value in named_roots.items():
            roots[name] = Path(path_value).resolve(strict=False)
        return roots

    @staticmethod
    def _root_name_for_role(role: str) -> str:
        if role == "config":
            return CONFIG_ROOT_NAME
        if role == "cache":
            return CACHE_ROOT_NAME
        if role == "data":
            return DATA_ROOT_NAME
        if role == "logs":
            return LOG_ROOT_NAME
        return DEFAULT_ROOT_NAME

    def _root_path_for(self, root_name: str) -> Path:
        try:
            return self._root_paths[root_name]
        except KeyError as error:
            raise CorylValidationError(f"Unknown managed root {root_name!r}.") from error

    @staticmethod
    def _validate_resource_name(name: str) -> None:
        if not isinstance(name, str) or not name.strip():
            raise TypeError("Resource name must be a non-empty string.")

    def _ensure_replaceable(self, name: str, *, replace: bool) -> None:
        if name in self._resources and not replace:
            raise ResourceConflictError(f"Resource '{name}' is already registered.")

    @staticmethod
    def _infer_kind(path_value: str | Path) -> ResourceKind:
        return "file" if Path(path_value).suffix else "directory"

    def _parse_manifest(self, manifest_data: Mapping[str, object]) -> dict[str, ResourceSpec]:
        self._validate_manifest_version(manifest_data)

        has_resources = "resources" in manifest_data
        has_legacy_paths = "paths" in manifest_data
        if has_resources and has_legacy_paths:
            raise ManifestFormatError("Manifest cannot define both 'resources' and legacy 'paths'.")
        if has_resources:
            resources_section = manifest_data["resources"]
            if not isinstance(resources_section, Mapping):
                raise ManifestFormatError("'resources' must be a mapping.")
            return self._parse_manifest_resource_mapping(resources_section)
        if has_legacy_paths:
            return self._parse_legacy_manifest(manifest_data["paths"])
        raise ManifestFormatError(
            "Manifest must contain either a top-level 'resources' mapping or legacy 'paths'."
        )

    def _parse_manifest_resource_mapping(
        self,
        resources_section: Mapping[str, object],
    ) -> dict[str, ResourceSpec]:
        parsed: dict[str, ResourceSpec] = {}
        for raw_name, definition in resources_section.items():
            name = self._coerce_resource_name(raw_name)
            if name in parsed:
                raise ManifestFormatError(f"Manifest defines duplicate resource name '{name}'.")
            parsed[name] = self._coerce_manifest_resource_spec(name, definition)
        return parsed

    def _parse_legacy_manifest(self, paths_section: object) -> dict[str, ResourceSpec]:
        if not isinstance(paths_section, Mapping):
            raise ManifestFormatError("'paths' must be a mapping.")

        files_section = paths_section.get("files", {})
        directories_section = paths_section.get("directories", {})

        if not isinstance(files_section, Mapping):
            raise ManifestFormatError("'paths.files' must be a mapping.")
        if not isinstance(directories_section, Mapping):
            raise ManifestFormatError("'paths.directories' must be a mapping.")

        parsed = self._parse_legacy_resource_section(files_section, kind="file")
        duplicates = sorted(set(parsed).intersection(self._legacy_names(directories_section)))
        if duplicates:
            joined_names = ", ".join(repr(name) for name in duplicates)
            raise ManifestFormatError(
                f"Legacy manifest defines duplicate resource names across files and directories: "
                f"{joined_names}."
            )

        parsed.update(self._parse_legacy_resource_section(directories_section, kind="directory"))
        return parsed

    def _parse_legacy_resource_section(
        self,
        section: Mapping[str, object],
        *,
        kind: ResourceKind,
    ) -> dict[str, ResourceSpec]:
        parsed: dict[str, ResourceSpec] = {}
        for raw_name, path_value in section.items():
            name = self._coerce_resource_name(raw_name)
            if name in parsed:
                raise ManifestFormatError(f"Manifest defines duplicate resource name '{name}'.")
            parsed[name] = self._coerce_manifest_resource_spec(
                name,
                {"path": path_value, "kind": kind},
            )
        return parsed

    def _coerce_manifest_resource_spec(
        self,
        name: str,
        definition: ResourceInput,
    ) -> ResourceSpec:
        try:
            return self._coerce_resource_spec(definition)
        except ManifestFormatError as error:
            raise ManifestFormatError(f"Resource '{name}' is invalid: {error}") from error
        except (CorylValidationError, ResourceKindError) as error:
            raise type(error)(f"Resource '{name}' is invalid: {error}") from error

    @staticmethod
    def _coerce_resource_name(raw_name: object) -> str:
        if not isinstance(raw_name, str) or not raw_name.strip():
            raise ManifestFormatError("Resource names must be non-empty strings.")
        return raw_name

    @staticmethod
    def _legacy_names(section: Mapping[str, object]) -> set[str]:
        names: set[str] = set()
        for raw_name in section:
            if isinstance(raw_name, str) and raw_name.strip():
                names.add(raw_name)
        return names

    @staticmethod
    def _coerce_bool_field(value: object, *, field_name: str) -> bool:
        if isinstance(value, bool):
            return value
        raise ManifestFormatError(f"Resource mapping '{field_name}' must be a boolean.")

    @staticmethod
    def _coerce_string_field(value: object, *, field_name: str) -> str:
        if isinstance(value, str):
            return value
        raise ManifestFormatError(f"Resource mapping '{field_name}' must be a string.")

    @staticmethod
    def _coerce_optional_string_field(value: object, *, field_name: str) -> str | None:
        if value is None:
            return None
        if isinstance(value, str):
            return value
        raise ManifestFormatError(f"Resource mapping '{field_name}' must be a string.")

    @staticmethod
    def _validate_manifest_version(manifest_data: Mapping[str, object]) -> None:
        version = manifest_data.get("version")
        if version is None:
            return
        if not isinstance(version, int) or isinstance(version, bool):
            raise ManifestFormatError(
                f"Manifest 'version' must be the integer {MANIFEST_VERSION}."
            )
        if version != MANIFEST_VERSION:
            raise ManifestFormatError(
                f"Unsupported manifest version {version}. "
                f"Coryl currently supports version {MANIFEST_VERSION}."
            )

    def _resolve_secrets_dir(
        self,
        secrets_dir: str | Path | None,
        *,
        root_name: str = DEFAULT_ROOT_NAME,
    ) -> Path | None:
        if secrets_dir is None:
            return None

        raw_path = validate_managed_path_input(secrets_dir, allow_absolute=True)
        if raw_path.is_absolute():
            return raw_path.resolve(strict=False)
        return self._resolve_from_named_root(raw_path, root_name=root_name)

    def _resolve_optional_rooted_path(
        self,
        path_value: str | Path | None,
        *,
        root_name: str = DEFAULT_ROOT_NAME,
    ) -> Path | None:
        if path_value is None:
            return None

        raw_path = validate_managed_path_input(path_value, allow_absolute=True)
        if raw_path.is_absolute():
            return raw_path.resolve(strict=False)
        return self._resolve_from_named_root(raw_path, root_name=root_name)

    @staticmethod
    def _normalize_layered_relative_paths(
        relative_path: str | Path | None,
        *,
        files: Sequence[str | Path] | None,
    ) -> tuple[Path, ...]:
        if files is not None:
            if isinstance(files, (str, Path)):
                raise TypeError(
                    "configs.layered() 'files' must be a sequence of paths, not a single path."
                )
            if relative_path is not None:
                raise TypeError(
                    "configs.layered() accepts either a positional path or 'files=', not both."
                )
            if not files:
                raise TypeError("configs.layered() 'files' must contain at least one path.")
            return tuple(Path(path_value) for path_value in files)

        if relative_path is None:
            raise TypeError("configs.layered() requires a path or a non-empty 'files' list.")
        return (Path(relative_path),)

    @staticmethod
    def _package_relative_path(relative_path: str | Path) -> Path:
        return validate_managed_path_input(relative_path)

    @classmethod
    def _resolve_package_assets(cls, package: str, relative_path: str | Path) -> Traversable:
        try:
            traversable = importlib_resources.files(package)
        except ModuleNotFoundError as error:
            raise CorylValidationError(f"Package '{package}' could not be imported.") from error

        package_path = cls._package_relative_path(relative_path)
        for part in package_path.parts:
            if part == ".":
                continue
            traversable = traversable.joinpath(part)

        if not traversable.is_dir():
            raise CorylValidationError(
                f"Package asset root '{package}:{package_path.as_posix()}' must be a directory."
            )
        return traversable


class Coryl(ResourceManager):
    """Brand-friendly alias for the main resource manager."""
