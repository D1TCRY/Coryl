# API Reference

This reference is generated from the code in `src/coryl`, not from README wording.

## Export Audit

Top-level names included in `coryl.__all__`:

`AssetGroup`, `CacheResource`, `ConfigResource`, `Coryl`, `CorylError`,
`CorylInvalidResourceKindError`, `CorylLockTimeoutError`,
`CorylOptionalDependencyError`, `CorylPathError`, `CorylReadOnlyResourceError`,
`CorylResourceNotFoundError`, `CorylUnsafePathError`,
`CorylUnsupportedFormatError`, `CorylValidationError`,
`LayeredConfigResource`, `MANIFEST_VERSION`, `ManifestFormatError`, `Resource`,
`ResourceConflictError`, `ResourceKindError`, `ResourceManager`,
`ResourceNotRegisteredError`, `ResourceSpec`, `UnsupportedFormatError`

Additional runtime-public names resolved by `coryl.__getattr__`:

`AssetNamespace`, `CacheNamespace`, `ConfigNamespace`, `DataNamespace`,
`DiskCacheResource`, `LogNamespace`, `PackageAssetGroup`,
`PackageAssetResource`, `ReadOnlyResourceError`, `ResourceKind`,
`ResourceRole`, `UnsafePathError`

Notes:

- `from coryl import *` only gets the names in `__all__`.
- `DiskCacheResource`, `PackageAssetGroup`, and `PackageAssetResource` are public at
  runtime, even though they are not in `__all__`.
- `ResourceKind` is `Literal["file", "directory"]`.
- `ResourceRole` is
  `Literal["resource", "config", "cache", "assets", "data", "logs"]`.
- When a return type below says `ManagedPath`, that is a local `Path` on the default
  filesystem and a `PurePosixPath` on fsspec-backed managers.

## Coryl Manager

### `Coryl`

```python
Coryl(
    root: str | Path,
    *,
    resources: Mapping[str, ResourceInput] | None = None,
    manifest_path: str | Path | None = None,
    create_missing: bool = True,
    filesystem: str | None = None,
    protocol: str | None = None,
    _named_roots: Mapping[str, str | Path] | None = None,
)
```

Short purpose:

Manage files and directories under a safe root, with namespaces for config, cache,
assets, data, and logs.

Return value:

A `Coryl` manager instance. `ResourceManager` is the same implementation with a less
brand-specific name.

Parameters:

| Parameter | Meaning |
| --- | --- |
| `root` | Base root for managed resources. |
| `resources` | Optional mapping passed through `register_many(...)` at startup. |
| `manifest_path` | Optional manifest file to load immediately. |
| `create_missing` | Default creation policy for registered resources. |
| `filesystem` | `None` or `"local"` for the default local backend, or `"fsspec"` for opt-in fsspec support. |
| `protocol` | fsspec protocol such as `"memory"` when `filesystem="fsspec"`. |
| `_named_roots` | Internal support for `for_app(...)`. Public to Python callers, but not intended for normal application code. |

Common exceptions:

- `ManifestFormatError` when `manifest_path` cannot be parsed into a valid manifest.
- `CorylValidationError` for invalid filesystem settings or invalid resource metadata.
- `CorylOptionalDependencyError` when optional fsspec support is requested without
  `coryl[fsspec]`.
- `TypeError` for invalid argument combinations such as `protocol=` without
  `filesystem="fsspec"`.

Optional dependency requirements:

- `with_fs(...)` or `filesystem="fsspec"` requires `coryl[fsspec]`.
- `for_app(...)` requires `coryl[platform]`.

Example:

```python
from coryl import Coryl

app = Coryl(root=".")
settings = app.configs.add("settings", "config/settings.toml")
cache = app.caches.add("http", ".cache/http")
logo = app.assets.add("ui", "assets/ui").file("images", "logo.svg", create=False)
```

Key classmethods:

| Signature | Purpose |
| --- | --- |
| `Coryl.with_fs(root, *, protocol=None, resources=None, manifest_path=None, create_missing=True) -> ResourceManager` | Build a manager on the fsspec backend. |
| `Coryl.for_app(app_name, app_author=None, version=None, roaming=False, multipath=False, ensure=True, create_missing=True) -> ResourceManager` | Build a local manager rooted in platform-specific config, cache, data, and log directories. |

Key properties:

| Property | Purpose |
| --- | --- |
| `root_path` | Main managed root. |
| `config_root_path`, `cache_root_path`, `data_root_path`, `log_root_path` | Named roots used by `for_app(...)`. |
| `named_roots` | Copy of the manager's named root mapping. |
| `manifest_path` | Loaded manifest path, if any. |
| `manifest` | Loaded manifest content, if any. |
| `config` | Alias for loaded manifest content. This is not an application settings resource. |
| `resources` | Copy of registered resources by name. |
| `configs`, `caches`, `assets`, `data`, `logs` | Typed namespaces for registration and lookup. |
| `file_paths`, `directory_paths`, `paths` | Collected resolved paths for registered local or fsspec resources. |
| `root_folder_path` | Legacy alias of `root_path`. |
| `config_file_path` | Manifest path when a manifest is loaded, otherwise the path of a registered file resource named `"config"`. |

Key methods:

| Signature | Purpose |
| --- | --- |
| `register(name, definition, *, replace=False) -> Resource` | Register from a `ResourceSpec`, a path, or a manifest-style mapping. |
| `register_many(resources, *, replace=False) -> dict[str, ManagedResource]` | Register several resources at once. |
| `register_file(...) -> Resource` | Register a regular file resource. |
| `register_directory(...) -> Resource` | Register a regular directory resource. |
| `register_config(...) -> ConfigResource` | Register a structured config file. |
| `register_layered_config(...) -> LayeredConfigResource` | Register a layered config resource on the local filesystem only. |
| `register_cache(...) -> CacheResource` | Register a cache directory. |
| `register_assets(...) -> AssetGroup` | Register an asset directory. |
| `register_package_assets(...) -> PackageAssetGroup` | Register a read-only package-backed asset directory. |
| `register_data(...) -> Resource` | Register a data resource under the data root. |
| `register_log(...) -> Resource` | Register a log resource under the log root. |
| `load_manifest(manifest_path) -> dict[str, object]` | Parse and register resources from a version 2 or legacy manifest. |
| `load_config() -> dict[str, object]` | Reload the currently loaded manifest. |
| `resource(name) -> ManagedResource` | Look up any registered resource. |
| `file(name) -> Resource` | Look up a resource and require `kind="file"`. |
| `directory(name) -> ManagedResource` | Look up a resource and require `kind="directory"`. |
| `config_resource(name="config") -> ConfigResource` | Look up a config resource. |
| `cache_resource(name) -> CacheResource` | Look up a cache resource. |
| `asset_group(name) -> AssetGroup | PackageAssetGroup` | Look up an asset resource. |
| `data_resource(name) -> Resource` | Look up a data resource. |
| `log_resource(name) -> Resource` | Look up a log resource. |
| `path(name) -> ManagedPath` | Return a resource path. |
| `content(name, default=MISSING) -> object` | Read a resource with auto-detected format. |
| `write_content(name, content) -> ManagedPath` | Write to a file resource using format-aware behavior. |
| `ensure(name) -> ManagedPath` | Create the target on disk or in fsspec storage when needed. |
| `resolve(*parts) -> ManagedPath` | Resolve a path under the main root without registering it. |
| `audit_paths() -> dict[str, object]` | Report existence, kind, role, path, and root safety for registered resources. |
| `is_child_of(child, parent) -> bool` | Static helper for root-confinement checks. |

Compatibility helpers:

- Dynamic attributes named `<resource>_file_path` and `<resource>_directory_path`
  still work for matching registered resources.
- `load_config()` and `config` are manifest helpers, not settings helpers.

### `ConfigNamespace`

```python
ConfigNamespace(manager: ResourceManager)
```

Short purpose:

Typed namespace exposed as `app.configs`.

Key methods:

| Signature | Purpose |
| --- | --- |
| `add(name, relative_path, *, create=None, encoding="utf-8", readonly=False, version=None, schema=None, replace=False) -> ConfigResource` | Register a config file. |
| `layered(name, relative_path=None, *, files=None, create=None, encoding="utf-8", readonly=False, env_prefix=None, secrets=None, required=False, secrets_dir=None, version=None, schema=None, replace=False) -> LayeredConfigResource` | Register layered config. |
| `get(name="config") -> ConfigResource` | Fetch a config by name. |
| `all() -> dict[str, ConfigResource]` | Return all registered config resources. |
| `names() -> list[str]` | Return config names. |

### `CacheNamespace`

```python
CacheNamespace(manager: ResourceManager)
```

Short purpose:

Typed namespace exposed as `app.caches`.

Key methods:

| Signature | Purpose |
| --- | --- |
| `add(name, relative_path, *, create=None, readonly=False, backend=None, replace=False) -> CacheResource` | Register a built-in or diskcache-backed cache. |
| `diskcache(name, relative_path, *, create=None, readonly=False, replace=False) -> DiskCacheResource` | Register a diskcache-backed cache directly. |
| `get(name) -> CacheResource` | Fetch a cache by name. |
| `all() -> dict[str, CacheResource]` | Return all registered caches. |
| `names() -> list[str]` | Return cache names. |

### `AssetNamespace`

```python
AssetNamespace(manager: ResourceManager)
```

Short purpose:

Typed namespace exposed as `app.assets`.

Key methods:

| Signature | Purpose |
| --- | --- |
| `add(name, relative_path, *, create=None, readonly=False, replace=False) -> AssetGroup` | Register a filesystem-backed asset directory. |
| `package(name, package, relative_path=".", *, readonly=True, replace=False) -> PackageAssetGroup` | Register package-backed assets under a specific package subdirectory. |
| `from_package(name, package, path="", *, replace=False) -> PackageAssetGroup` | Convenience alias for package-backed assets when the package root is enough. |
| `get(name) -> AssetGroup | PackageAssetGroup` | Fetch an asset group. |
| `all() -> dict[str, AssetGroup | PackageAssetGroup]` | Return all asset resources. |
| `names() -> list[str]` | Return asset names. |

## ResourceSpec

```python
ResourceSpec(
    relative_path: Path,
    kind: ResourceKind = "file",
    create: bool = True,
    encoding: str = "utf-8",
    role: ResourceRole = "resource",
    readonly: bool = False,
    required: bool = False,
    format: str | None = None,
    schema: str | None = None,
    backend: str | None = None,
)
```

Short purpose:

Declarative resource metadata. Use it when you want to pass a resource definition into
`Coryl.register(...)` or build manifest-like objects in Python.

Return value:

A frozen dataclass describing the resource to register.

Parameters:

| Parameter | Meaning |
| --- | --- |
| `relative_path` | Managed relative path. |
| `kind` | `"file"` or `"directory"`. |
| `create` | Whether registration should ensure the path exists immediately. |
| `encoding` | Default text encoding. |
| `role` | One of `resource`, `config`, `cache`, `assets`, `data`, `logs`. |
| `readonly` | Block mutations when `True`. |
| `required` | Mark manifest or layered resources as required. |
| `format` | Optional explicit structured format name in manifest data. |
| `schema` | Optional schema name in manifest data. |
| `backend` | Optional backend marker such as `"diskcache"`. |

Common exceptions:

- `CorylValidationError` for invalid booleans, roles, encodings, or incompatible
  role/kind combinations.
- `ResourceKindError` for invalid `kind` values.

Optional dependency requirements:

None by itself.

Factory methods:

| Signature | Purpose |
| --- | --- |
| `ResourceSpec.file(path, *, create=True, encoding="utf-8", readonly=False, required=False, format=None, schema=None, backend=None)` | File resource. |
| `ResourceSpec.directory(path, *, create=True, encoding="utf-8", readonly=False, required=False, format=None, schema=None, backend=None)` | Directory resource. |
| `ResourceSpec.config(path, *, create=True, encoding="utf-8", readonly=False, required=False, format=None, schema=None, backend=None)` | Config file resource. |
| `ResourceSpec.cache(path, *, create=True, encoding="utf-8", readonly=False, required=False, format=None, schema=None, backend=None)` | Cache directory resource. |
| `ResourceSpec.assets(path, *, create=True, encoding="utf-8", readonly=False, required=False, format=None, schema=None, backend=None)` | Asset directory resource. |
| `ResourceSpec.data(path, *, create=True, encoding="utf-8", readonly=False, required=False, format=None, schema=None, backend=None)` | Data resource. File vs directory is inferred from the suffix. |
| `ResourceSpec.logs(path, *, create=True, encoding="utf-8", readonly=False, required=False, format=None, schema=None, backend=None)` | Log resource. File vs directory is inferred from the suffix. |

Example:

```python
from coryl import Coryl, ResourceSpec

app = Coryl(".")
app.register(
    "settings",
    ResourceSpec.config("config/settings.toml", create=False, readonly=True),
)
```

## Resource

```python
Resource(
    name: str,
    path: ManagedPath,
    kind: ResourceKind,
    filesystem: LocalFS | FsspecFS,
    create: bool = True,
    encoding: str = "utf-8",
    role: ResourceRole = "resource",
    readonly: bool = False,
    required: bool = False,
    declared_format: str | None = None,
    schema: str | None = None,
    backend: str | None = None,
    typed_schema: type[object] | None = None,
    managed_root: ManagedPath | None = None,
    root_name: str = "root",
)
```

Short purpose:

Concrete file or directory resource. In normal application code you usually get one
from `register_file(...)`, `register_directory(...)`, `joinpath(...)`, or one of the
typed namespaces instead of constructing it directly.

Return value:

A resource bound to a resolved local or fsspec path.

Common exceptions:

- `ResourceKindError` when file-only helpers are used on directories, or the reverse.
- `CorylReadOnlyResourceError` when writes are attempted on read-only resources.
- `CorylValidationError` when local-only helpers are used on fsspec resources.
- `CorylOptionalDependencyError` for YAML, lock, or watch helpers when the matching
  optional package is missing.
- `UnsupportedFormatError` for unsupported structured formats.

Optional dependency requirements:

- YAML helpers need `coryl[yaml]` for `.yaml` and `.yml`.
- `lock()` needs `coryl[lock]`.
- `watch()` needs `coryl[watch]`.

Key methods:

| Signature | Purpose |
| --- | --- |
| `ensure() -> ManagedPath` | Create the file or directory if needed. |
| `exists() -> bool` | Check existence. |
| `is_file() -> bool` | Check file kind on the backend. |
| `is_dir() -> bool` | Check directory kind on the backend. |
| `open(*args, **kwargs) -> IO[str] | IO[bytes]` | Open a file resource on the local filesystem only. |
| `read_text(*, encoding=None) -> str` | Read text. |
| `write_text(content, *, encoding=None, atomic=True) -> ManagedPath` | Write text. Local writes are atomic by default. |
| `read_bytes() -> bytes` | Read bytes. |
| `write_bytes(content, *, atomic=True) -> ManagedPath` | Write bytes. |
| `read_data(*, default=MISSING, encoding=None) -> object` | Read JSON, TOML, or YAML based on the file extension. |
| `write_data(content, *, encoding=None, atomic=True) -> ManagedPath` | Write structured data using the file extension. |
| `read_json(...)`, `write_json(...)` | JSON-specific structured helpers. |
| `read_toml(...)`, `write_toml(...)` | TOML-specific structured helpers. |
| `read_yaml(...)`, `write_yaml(...)` | YAML-specific structured helpers. |
| `content(*, default=MISSING) -> object` | Auto-read bytes, text, or structured content. |
| `write(content) -> ManagedPath` | Auto-write structured data when the extension is recognized, otherwise text or bytes. |
| `joinpath(*parts, kind=None, create=False, role="resource") -> Resource` | Create a managed child resource under a directory resource. |
| `iterdir() -> Iterator[ManagedPath]` | Iterate direct children of a directory resource. |
| `glob(pattern: str) -> list[ManagedPath]` | Globbing under a directory resource. |
| `lock(timeout=None) -> Iterator[Resource]` | Acquire a local file lock and yield the resource. |
| `watch(...) -> Iterator[WatchChanges]` | Blocking filesystem watch iterator for the local filesystem. |

Example:

```python
from coryl import Coryl

app = Coryl(".")
report = app.register_file("report", "build/report.json", create=False)
report.write_json({"ok": True})
print(report.read_json())
```

## ConfigResource

```python
ConfigResource(
    name: str,
    path: ManagedPath,
    kind: ResourceKind,
    filesystem: LocalFS | FsspecFS,
    create: bool = True,
    encoding: str = "utf-8",
    role: ResourceRole = "resource",
    readonly: bool = False,
    required: bool = False,
    declared_format: str | None = None,
    schema: str | None = None,
    backend: str | None = None,
    typed_schema: type[object] | None = None,
    managed_root: ManagedPath | None = None,
    root_name: str = "root",
    version: int | None = None,
)
```

Short purpose:

Structured config file resource. Supported formats are `.json`, `.toml`, `.yaml`, and
`.yml`.

Return value:

A `ConfigResource` with mapping helpers, migration helpers, and optional typed-loading
helpers.

Parameters:

The constructor inherits `Resource` parameters and adds `version`, which is the target
document version used by `migrate()`.

Common exceptions:

- `UnsupportedFormatError` when the config file does not use a supported extension.
- `CorylValidationError` for invalid migration metadata or missing required config
  keys.
- `CorylReadOnlyResourceError` for blocked writes or migrations.
- `CorylOptionalDependencyError` for watch or typed-config helpers when optional
  packages are missing.
- `TypeError` when `update(...)` or `migrate()` is used on non-mapping config data.

Optional dependency requirements:

- Typed helpers need `coryl[pydantic]` and expect a Pydantic v2-style
  `model_validate()` / `model_dump()` interface.
- Watch helpers need `coryl[watch]`.
- YAML configs need `coryl[yaml]`.

Typed-schema note:

- `app.configs.add(..., schema=MyModel)` and `register_config(..., schema=MyModel)`
  register a typed model for `load_typed()`.
- Manifest fields such as `schema = "app.settings.v1"` are stored as metadata on the
  resource, but they are not used as typed model classes.

Key methods:

| Signature | Purpose |
| --- | --- |
| `load(*, default=MISSING) -> object` | Load the full config document. Empty structured files load as `{}`. |
| `save(content, *, atomic=True) -> ManagedPath` | Save the full config document. |
| `get(key_path, default=None) -> object` | Read dotted config paths such as `"database.host"` or `"items.0.name"`. |
| `require(key_path, default=MISSING) -> object` | Same as `get(...)`, but raises when the value is missing and no default is supplied. |
| `update(*mappings, lock=False, **changes) -> dict[str, object]` | Shallow-merge mapping content into the current document and save it. |
| `migration(*, from_version, to_version)` | Decorator used to register version-to-version migration functions. |
| `migrate() -> dict[str, object]` | Apply registered migrations until `version` is reached, then save the result. |
| `load_typed(model=None) -> TValidated | object` | Validate the loaded document with an explicit model or the resource's registered schema. |
| `save_typed(instance, *, atomic=True) -> ManagedPath` | Save a typed instance via `model_dump(mode="json")`. |
| `watch_reload(...) -> Iterator[object]` | Blocking iterator that reloads the config after each relevant filesystem change. |
| `on_change(callback, ...) -> None` | Call a callback with the reloaded document after each relevant filesystem change. |

Example:

```python
from coryl import Coryl

app = Coryl(".")
settings = app.configs.add("settings", "config/settings.toml", version=2)
settings.save({"version": 1, "theme": "light"})

@settings.migration(from_version=1, to_version=2)
def migrate_v2(document: dict[str, object]) -> dict[str, object]:
    document["appearance"] = {"theme": document.pop("theme")}
    return document

print(settings.migrate())
```

## LayeredConfigResource

```python
LayeredConfigResource(
    name: str,
    path: ManagedPath,
    kind: ResourceKind,
    filesystem: LocalFS | FsspecFS,
    create: bool = True,
    encoding: str = "utf-8",
    role: ResourceRole = "resource",
    readonly: bool = False,
    required: bool = False,
    declared_format: str | None = None,
    schema: str | None = None,
    backend: str | None = None,
    typed_schema: type[object] | None = None,
    managed_root: ManagedPath | None = None,
    root_name: str = "root",
    version: int | None = None,
    layer_paths: tuple[Path, ...] = (),
    env_prefix: str | None = None,
    secrets_path: Path | None = None,
    secrets_dir: Path | None = None,
    runtime_overrides: dict[str, object] = ...,
)
```

Short purpose:

Layer a small number of config files with optional secrets, environment overrides, and
runtime overrides.

Public status:

`LayeredConfigResource` is top-level public and is also returned by
`app.configs.layered(...)` and `app.register_layered_config(...)`.

Return value:

A config resource whose read view is merged and whose write target is the primary base
file.

Parameters:

In normal code you do not construct this directly. Use `configs.layered(...)` or
`register_layered_config(...)` and provide:

| Parameter | Meaning |
| --- | --- |
| `relative_path` or `files=[...]` | The primary writable config path, or an ordered list of layer files. |
| `env_prefix` | Prefix for environment overrides such as `MYAPP_DATABASE__HOST`. |
| `secrets` | Optional structured secrets file. |
| `secrets_dir` | Optional directory whose filenames become top-level keys. |
| `required` | When `True`, missing layer files or secrets inputs raise instead of being skipped. |
| `version`, `schema` | Reuse `ConfigResource` migration and typed-config helpers. |

Common exceptions:

- `CorylValidationError` when the manager is not local, when `secrets` and
  `secrets_dir` are both supplied, or when override syntax is invalid.
- `UnsupportedFormatError` when any layer file or secrets file does not use
  `.json`, `.toml`, `.yaml`, or `.yml`.
- `FileNotFoundError` when a required layer or secrets directory is missing.
- `TypeError` when overrides are not mapping data or `KEY=VALUE` strings.

Optional dependency requirements:

- Local filesystem only.
- YAML layers need `coryl[yaml]`.
- Typed helpers need `coryl[pydantic]`.
- Watch helpers need `coryl[watch]`.

Key methods:

| Signature | Purpose |
| --- | --- |
| `load(*, default=MISSING) -> object` | Return the merged document from files, secrets, environment, and runtime overrides. |
| `load_base(*, default=MISSING) -> object` | Read only the primary writable config file, not the merged view. |
| `as_dict() -> dict[str, object]` | Return the merged config as a copied mapping. |
| `override(values: Mapping[str, object]) -> dict[str, object]` | Apply runtime overrides from a mapping. Dotted keys are supported. |
| `apply_overrides(values: Iterable[str]) -> dict[str, object]` | Apply runtime overrides from `KEY=VALUE` strings. |
| `reload() -> dict[str, object]` | Recompute and return the merged view. |
| `update(*mappings, lock=False, **changes) -> dict[str, object]` | Update and save only the primary writable file. |
| `save(...)`, `save_typed(...)`, `migrate(...)`, `watch_reload(...)`, `on_change(...)` | Inherited from `ConfigResource`. They operate on the writable base file or on the merged watch view as implemented. |

Merge order:

1. `files=[...]` or the single `relative_path`
2. `secrets=...`
3. `secrets_dir=...`
4. environment variables from `env_prefix=...`
5. runtime overrides from `override(...)` and `apply_overrides(...)`

Merge rules:

- mappings are deep-merged
- lists are replaced
- scalars are replaced

Example:

```python
from coryl import Coryl

app = Coryl(".")
settings = app.configs.layered(
    "settings",
    files=["config/defaults.toml", "config/local.toml"],
    env_prefix="MYAPP",
)

settings.override({"database.host": "localhost"})
print(settings.as_dict())
```

## CacheResource

```python
CacheResource(
    name: str,
    path: ManagedPath,
    kind: ResourceKind,
    filesystem: LocalFS | FsspecFS,
    create: bool = True,
    encoding: str = "utf-8",
    role: ResourceRole = "resource",
    readonly: bool = False,
    required: bool = False,
    declared_format: str | None = None,
    schema: str | None = None,
    backend: str | None = None,
    typed_schema: type[object] | None = None,
    managed_root: ManagedPath | None = None,
    root_name: str = "root",
)
```

Short purpose:

Inspectable file-backed cache directory with TTL metadata managed by Coryl.

Return value:

A cache directory resource whose entries are regular managed files.

Common exceptions:

- `CorylReadOnlyResourceError` when mutation helpers are used on a read-only cache.
- `CorylPathError` or `CorylUnsafePathError` for absolute, traversal, or escaping
  cache keys.
- `CorylValidationError` when a reserved Coryl metadata filename is used.
- `FileNotFoundError` when `delete(..., missing_ok=False)` targets a missing entry.

Optional dependency requirements:

- No extra is required for the built-in cache.
- YAML cache entries need `coryl[yaml]`.

Key methods:

| Signature | Purpose |
| --- | --- |
| `entry(*parts, kind=None, create=False) -> Resource` | Return a managed child resource inside the cache directory. |
| `file(*parts, create=False) -> Resource` | Return a file entry resource. |
| `directory(*parts, create=False) -> CacheResource` | Return a nested cache directory. |
| `set(key, value, ttl=None) -> ManagedPath` | Store a value. The format is inferred from the entry path. |
| `get(key, default=None) -> object` | Read a cached value or return the default. |
| `load(*parts, default=MISSING) -> object` | Read a cached value by multipart path. |
| `has(key) -> bool` | Check whether the entry exists and has not expired. |
| `remember(key_or_path, *parts, factory=None, content=MISSING, ttl=None) -> object` | Return a cached value or create and store one. |
| `remember_json(path, factory, ttl=None) -> object` | JSON-specific convenience helper. |
| `remember_text(path, factory, ttl=None) -> str` | Text-specific convenience helper. |
| `delete(*parts, missing_ok=True) -> None` | Remove one cached entry. |
| `clear() -> None` | Remove all cache content. |
| `expire() -> int` | Remove expired entries and return the number removed. |

Behavior notes:

- TTL tracking for the built-in cache is file-based. Coryl maintains an internal
  metadata file named `.coryl-cache-index.json` inside the cache directory.
- That metadata filename is reserved and should not be used as an application cache
  key.
- For backward compatibility, `remember("dir", "file.json", content=...)` returns the
  stored path instead of the cached value.

Example:

```python
from coryl import Coryl

app = Coryl(".")
cache = app.caches.add("http", ".cache/http")
user = cache.remember_json("users/42.json", lambda: {"id": 42, "name": "Ada"})
print(user["name"])
```

## DiskCacheResource

```python
DiskCacheResource(
    name: str,
    path: ManagedPath,
    kind: ResourceKind,
    filesystem: LocalFS | FsspecFS,
    create: bool = True,
    encoding: str = "utf-8",
    role: ResourceRole = "resource",
    readonly: bool = False,
    required: bool = False,
    declared_format: str | None = None,
    schema: str | None = None,
    backend: str | None = None,
    typed_schema: type[object] | None = None,
    managed_root: ManagedPath | None = None,
    root_name: str = "root",
)
```

Short purpose:

Disk-backed cache resource backed by the third-party `diskcache.Cache` class.

Public status:

`DiskCacheResource` is runtime-public and importable from `coryl`, even though it is
not part of `coryl.__all__`.

Return value:

A cache resource that stores values in `diskcache` instead of regular files.

Common exceptions:

- `CorylOptionalDependencyError` when `diskcache` is not installed.
- `CorylValidationError` when used on a non-local manager.
- `CorylReadOnlyResourceError` for blocked mutations.
- `CorylPathError` or `CorylUnsafePathError` for invalid path-style string keys.
- `KeyError` from `load(...)` or `delete(..., missing_ok=False)` when a key is
  missing.

Optional dependency requirements:

- `coryl[diskcache]`
- Local filesystem only

Key methods and properties:

| Signature | Purpose |
| --- | --- |
| `raw -> object` | Lazily created underlying `diskcache.Cache` instance. |
| `set(key, value, ttl=None) -> ManagedPath` | Store a value in the diskcache backend. |
| `get(key, default=None) -> object` | Read a value from the backend. |
| `load(*parts, default=MISSING) -> object` | Read by key or multipart path. |
| `has(key) -> bool` | Membership test against the backend. |
| `delete(key_or_path, *parts, missing_ok=True) -> None` | Remove a key. |
| `clear() -> None` | Clear the backend. |
| `expire() -> int` | Run backend expiration and return the number removed. |
| `remember(key_or_path, *parts, factory=None, content=MISSING, ttl=None) -> object` | Cache-or-build helper. |
| `remember_json(path, factory, ttl=None) -> object` | Alias to `remember(...)` for path-style JSON use. |
| `remember_text(path, factory, ttl=None) -> str` | Text-specific convenience helper. |
| `memoize(ttl=None)` | Return the backend's decorator for memoized function calls. |

Key behavior differences from `CacheResource`:

- Path-style string keys such as `"users/42.json"` are validated for safety.
- Arbitrary non-path keys are also allowed because the backend accepts them directly.
- Values are stored as Python objects in `diskcache`, not as inspectable application
  files.

Example:

```python
from coryl import Coryl

app = Coryl(".")
cache = app.caches.diskcache("api", ".cache/api")

@cache.memoize(ttl=60)
def load_user(user_id: int) -> dict[str, object]:
    return {"id": user_id}

print(load_user(42))
```

## AssetGroup

```python
AssetGroup(
    name: str,
    path: ManagedPath,
    kind: ResourceKind,
    filesystem: LocalFS | FsspecFS,
    create: bool = True,
    encoding: str = "utf-8",
    role: ResourceRole = "resource",
    readonly: bool = False,
    required: bool = False,
    declared_format: str | None = None,
    schema: str | None = None,
    backend: str | None = None,
    typed_schema: type[object] | None = None,
    managed_root: ManagedPath | None = None,
    root_name: str = "root",
)
```

Short purpose:

Managed filesystem asset directory with safe child lookups.

Return value:

An asset directory resource.

Common exceptions:

- `CorylUnsafePathError` for traversal or escaping child paths.
- `CorylReadOnlyResourceError` when creating children under a read-only group.
- `FileNotFoundError` from `require(...)` for missing assets.

Optional dependency requirements:

- YAML helpers on child resources still need `coryl[yaml]`.
- Watch helpers on child resources still need `coryl[watch]`.

Key methods:

| Signature | Purpose |
| --- | --- |
| `file(*parts, create=False) -> Resource` | Return a file resource inside the asset group. |
| `directory(*parts, create=False) -> AssetGroup` | Return a nested asset directory. |
| `require(*parts, kind=None) -> Resource` | Require an existing asset child. |
| `files(pattern="**/*") -> list[ManagedPath]` | Return files only. |
| `glob(pattern) -> list[ManagedPath]` | Return files and directories that match the pattern. |

Example:

```python
from coryl import Coryl

app = Coryl(".")
assets = app.assets.add("ui", "assets/ui")
logo = assets.require("images", "logo.svg")
print(logo.path)
```

## PackageAssetGroup

```python
PackageAssetGroup(
    name: str,
    package: str,
    traversable: Traversable,
    package_path: PurePosixPath,
    relative_path: PurePosixPath,
    readonly: bool = True,
    role: ResourceRole = "assets",
    kind: ResourceKind = "directory",
    encoding: str = "utf-8",
)
```

Short purpose:

Read-only asset group backed by `importlib.resources`.

Public status:

`PackageAssetGroup` is runtime-public and importable from `coryl`, even though it is
not part of `coryl.__all__`.

Return value:

A package-backed asset directory that works from a source tree, a normal install, or a
zipped import.

Common exceptions:

- `CorylReadOnlyResourceError` for attempted writes or attempted `create=True`.
- `CorylPathError` when code asks for a stable filesystem `path`.
- `CorylUnsafePathError` for traversal in child lookups or unsafe copy targets.
- `FileNotFoundError` from `require(...)` for missing package resources.
- `ResourceKindError` when a caller asks for a file but the resource is a directory,
  or the reverse.

Optional dependency requirements:

None.

Key methods:

| Signature | Purpose |
| --- | --- |
| `exists(*parts) -> bool` | Check whether a child exists. |
| `file(*parts, create=False) -> PackageAssetResource` | Return a package-backed file handle. |
| `directory(*parts, create=False) -> PackageAssetGroup` | Return a package-backed subdirectory handle. |
| `require(*parts, kind=None) -> PackageAssetResource | PackageAssetGroup` | Require an existing child. |
| `read_text(*parts, encoding="utf-8") -> str` | Read a package file directly. |
| `read_bytes(*parts) -> bytes` | Read bytes directly. |
| `as_file(*parts)` | Materialize one file as a temporary local `Path`. |
| `files(pattern="**/*") -> list[PackageAssetResource]` | Return matching package file handles. |
| `copy_to(target_directory, *, overwrite=False) -> Path` | Copy the full asset tree to a local directory. |

Important path limitation:

`PackageAssetGroup.path` always raises `CorylPathError`. Package resources do not have
a stable on-disk directory path.

Read-only note:

Package assets are always read-only. The registration helpers accept `readonly=...`,
but the created package-backed resource still behaves as read-only.

### `PackageAssetResource`

`PackageAssetGroup.file(...)` returns `PackageAssetResource`, which is also
runtime-public.

```python
PackageAssetResource(
    name: str,
    package: str,
    traversable: Traversable,
    package_path: PurePosixPath,
    relative_path: PurePosixPath,
    kind: ResourceKind = "file",
    readonly: bool = True,
    role: ResourceRole = "assets",
    encoding: str = "utf-8",
)
```

Key methods and properties:

| Signature | Purpose |
| --- | --- |
| `display_path -> str` | `package://...` display path for the file. |
| `path` | Always raises `CorylPathError`. |
| `exists() -> bool` | Check availability. |
| `is_file() -> bool` | Check file status. |
| `is_dir() -> bool` | Check directory status. |
| `read_text(*, encoding="utf-8") -> str` | Read text from the package resource. |
| `read_bytes() -> bytes` | Read bytes from the package resource. |
| `open(*args, **kwargs)` | Open the package resource for reading. |
| `as_file()` | Materialize one temporary local file path. |

Example:

```python
from coryl import Coryl

app = Coryl(".")
templates = app.assets.from_package("templates", "myapp.assets_pkg", path="templates")
print(templates.read_text("email.html"))

with templates.file("email.html").as_file() as temp_path:
    print(temp_path)
```

## Data/Log Namespaces

### `DataNamespace`

```python
DataNamespace(manager: ResourceManager)
```

Short purpose:

Typed namespace exposed as `app.data`.

Return value:

Plain `Resource` objects with `role == "data"`.

Key methods:

| Signature | Purpose |
| --- | --- |
| `add(name, relative_path, *, create=None, encoding="utf-8", readonly=False, replace=False) -> Resource` | Register a data file or directory. |
| `get(name) -> Resource` | Fetch a data resource. |
| `all() -> dict[str, Resource]` | Return all data resources. |
| `names() -> list[str]` | Return data resource names. |

Example:

```python
state = app.data.add("state", "data/state.json")
state.write_json({"count": 1})
```

### `LogNamespace`

```python
LogNamespace(manager: ResourceManager)
```

Short purpose:

Typed namespace exposed as `app.logs`.

Return value:

Plain `Resource` objects with `role == "logs"`.

Key methods:

| Signature | Purpose |
| --- | --- |
| `add(name, relative_path, *, create=None, encoding="utf-8", readonly=False, replace=False) -> Resource` | Register a log file or directory. |
| `get(name) -> Resource` | Fetch a log resource. |
| `all() -> dict[str, Resource]` | Return all log resources. |
| `names() -> list[str]` | Return log resource names. |

Example:

```python
log_file = app.logs.add("main", "logs/app.log")
log_file.write_text("started\n")
```

## Exceptions

All public Coryl exceptions inherit from `CorylError`.

| Name | Base classes | Meaning |
| --- | --- | --- |
| `CorylError` | `Exception` | Base exception for the package. |
| `CorylValidationError` | `CorylError`, `ValueError` | Invalid resource metadata, invalid config content, or invalid Coryl-specific arguments. |
| `CorylPathError` | `CorylValidationError` | Managed path is malformed for Coryl's safety model. |
| `CorylUnsafePathError` | `CorylPathError` | Managed path would escape its allowed root. |
| `CorylResourceNotFoundError` | `CorylError`, `KeyError` | Named resource is not registered. |
| `CorylInvalidResourceKindError` | `CorylError`, `TypeError` | Resource kind is invalid or used incorrectly. |
| `CorylUnsupportedFormatError` | `CorylValidationError` | Unsupported file format for a requested structured operation. |
| `CorylOptionalDependencyError` | `CorylError`, `ImportError` | Optional package is required for the requested feature. |
| `CorylLockTimeoutError` | `CorylError`, `TimeoutError` | A file lock could not be acquired in time. |
| `CorylReadOnlyResourceError` | `CorylError`, `PermissionError` | Mutation was attempted on a read-only resource. |
| `ResourceConflictError` | `CorylValidationError` | Resource name was registered twice without `replace=True`. |
| `ManifestFormatError` | `CorylValidationError` | Manifest file exists but cannot be interpreted as a valid Coryl manifest. |

Public aliases:

| Alias | Target |
| --- | --- |
| `ResourceNotRegisteredError` | `CorylResourceNotFoundError` |
| `ResourceKindError` | `CorylInvalidResourceKindError` |
| `UnsafePathError` | `CorylUnsafePathError` |
| `UnsupportedFormatError` | `CorylUnsupportedFormatError` |
| `ReadOnlyResourceError` | `CorylReadOnlyResourceError` |

Example:

```python
from coryl import Coryl, ResourceNotRegisteredError

app = Coryl(".")

try:
    app.resource("missing")
except ResourceNotRegisteredError:
    print("not registered")
```

## CLI Commands

Console entry point:

```python
coryl.cli.main(
    argv: Sequence[str] | None = None,
    *,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int
```

Short purpose:

Run the built-in diagnostics CLI that ships with the package.

Return value:

Exit code `0` for success, `1` for handled command errors. `resources check` also
returns `1` when a resource is missing or unsafe.

Common exceptions:

The CLI catches `CorylError`, `FileNotFoundError`, `KeyError`, `TypeError`, and
`ValueError`, prints `Error: ...` to `stderr`, and returns `1`.

Optional dependency requirements:

- No extra is required for the CLI entry point itself.
- YAML manifests or YAML config files still need `coryl[yaml]`.
- `cache clear` against a `backend="diskcache"` cache needs `coryl[diskcache]`.

Global flags:

| Flag | Purpose |
| --- | --- |
| `--manifest PATH` | Manifest path relative to `--root`. Default: `app.toml`. |
| `--root PATH` | Project root used to resolve resources. Default: `.` |
| `--json` | Emit JSON instead of the table view. |

Commands:

### `coryl resources list`

```text
coryl resources list [--manifest PATH] [--root PATH] [--json]
```

Purpose:

Load the manifest and list registered resources with their role, kind, existence, path,
and safety status.

### `coryl resources check`

```text
coryl resources check [--manifest PATH] [--root PATH] [--json]
```

Purpose:

Load the manifest and report missing or unsafe resources. Exit code is `1` when any
problem is found.

### `coryl config show NAME`

```text
coryl config show NAME [--manifest PATH] [--root PATH] [--json]
```

Purpose:

Load one config resource from the manifest and print its current content.

### `coryl cache clear NAME`

```text
coryl cache clear NAME [--manifest PATH] [--root PATH] [--json]
```

Purpose:

Clear one cache resource from the manifest and report whether it existed beforehand.

### `coryl assets list NAME`

```text
coryl assets list NAME [--manifest PATH] [--root PATH] [--json]
```

Purpose:

List files inside a filesystem asset group or a package-backed asset group.

Example:

```bash
coryl resources list --manifest app.toml --root .
coryl config show settings --manifest app.toml --root . --json
```
