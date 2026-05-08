# Coryl

Coryl is a Python library for managing application resources from a single root directory.

It is designed for projects that need to work with:

- configuration files
- cache folders
- static assets
- runtime data files
- documents, images, and bundled resources

Coryl gives you one place to declare these resources, keeps them inside a safe root folder, and provides high-level helpers for JSON, TOML, YAML, text, and binary files.

## Features

- Safe path resolution relative to one application root
- Automatic creation of missing files and directories when desired
- Built-in support for `.json`, `.toml`, `.yaml`, and `.yml`
- Specialized APIs for `configs`, `caches`, and `assets`
- Optional app-directory support through `platformdirs`
- Explicit read-only resources for mounted config, cache, and asset paths
- Generic file and directory management when you do not need special behavior
- Versioned manifest loading from JSON, TOML, or YAML with legacy compatibility
- Compatibility helpers for older `FileManager`-style code

## Installation

```bash
pip install coryl
```

Optional diagnostics CLI support:

```bash
pip install coryl[cli]
```

The diagnostics CLI is optional tooling for Coryl-managed projects. It is not required for normal library usage.

Optional file locking support:

```bash
pip install coryl[lock]
```

Optional DiskCache backend for heavier persistent caches:

```bash
pip install coryl[diskcache]
```

Optional advanced fsspec-backed filesystems:

```bash
pip install coryl[fsspec]
```

Optional platform-aware app roots:

```bash
pip install coryl[platform]
```

Optional typed config validation with Pydantic:

```bash
pip install coryl[pydantic]
```

Optional file watching and config reload helpers:

```bash
pip install coryl[watch]
```

Python 3.10+ is supported.

## Core Idea

You create a `Coryl` manager bound to one root folder. Every managed resource is declared relative to that root.

```python
from coryl import Coryl

app = Coryl(root=".")
```

From there you can register:

- generic files
- generic directories
- config files
- cache directories
- persistent app data
- log files and directories
- asset directories

## Quick Start

```python
from coryl import Coryl

app = Coryl(root=".")

settings = app.configs.add("settings", "config/settings.toml")
http_cache = app.caches.add("http", ".cache/http")
ui_assets = app.assets.add("ui", "assets/ui")

settings.save(
    {
        "app_name": "Coryl Demo",
        "debug": True,
        "database": {"host": "localhost", "port": 5432},
    }
)

users = http_cache.remember_json(
    "responses/users.json",
    lambda: {"count": 42},
    ttl=300,
)
state = http_cache.remember_text("tokens/state.txt", lambda: "ready", ttl=60)
logo = ui_assets.file("images", "logo.svg", create=False)

print(settings.load())
print(users)
print(state)
print(logo.path)
```

## Concepts

### Root Folder

Every resource is resolved relative to a single root folder:

```python
app = Coryl(root="/path/to/project")
```

Coryl refuses to register or create managed resources outside that root.
Registration paths are expected to be relative to `root`, so absolute paths are rejected by default and traversal segments such as `..` are not accepted.

### Advanced Filesystems

Most users should keep the default local `pathlib` behavior:

```python
app = Coryl(root=".")
```

If you need an `fsspec` backend for a local or remote filesystem, install the optional extra and opt in explicitly:

```bash
pip install coryl[fsspec]
```

```python
from coryl import Coryl

app = Coryl.with_fs(root="memory://app", protocol="memory")
# or:
app = Coryl(root="memory://app", filesystem="fsspec")
```

This is intentionally an advanced, conservative feature in the first release. The default local flow is still the recommended path, and you do not need `fsspec` for normal Coryl usage.

Current fsspec support is focused on basic file and directory operations:

- file registration and directory registration
- text and binary reads and writes
- JSON, TOML, and YAML reads and writes through Coryl's normal resource helpers
- directory creation and simple glob-based listing

Current limitations:

- `resource.path` stays a real `Path` for the default local filesystem, but fsspec-backed resources expose logical managed paths rather than a local on-disk path
- path confinement still applies logically inside the configured root, but backend-specific escape rules are not exhaustively modeled in this first version
- atomic writes are only guaranteed on the default local filesystem; fsspec backends may fall back to direct writes
- locks, file watching, layered config helpers, and the `diskcache` backend currently require the default local filesystem

### Installed Applications

If you are writing an installed CLI, desktop app, or service, you can let Coryl use OS-specific application directories through `platformdirs`.

Install the optional extra:

```bash
pip install coryl[platform]
```

Then create the manager with `Coryl.for_app(...)`:

```python
from coryl import Coryl

app = Coryl.for_app("mytool", app_author="Acme")

settings = app.configs.add("settings", "settings.toml")
cache = app.caches.add("http", "http")
data = app.data.add("state", "state.json")
log = app.logs.add("main", "app.log")
```

`Coryl(root=".")` stays unchanged. `for_app()` simply routes:

- `app.configs` into the platform config directory
- `app.caches` into the platform cache directory
- `app.data` into the platform data directory
- `app.logs` into the platform log directory

The `assets` namespace still works as before. In app mode it remains rooted under the manager's main root, which defaults to the application data directory.

### Resource Types

Coryl works with four main categories:

- `Resource`: generic file or directory
- `ConfigResource`: structured config file
- `CacheResource`: cache directory with file-oriented helpers
- `AssetGroup`: asset directory with lookup helpers

### Structured Formats

Structured files are detected automatically from their extension:

- `.json`
- `.toml`
- `.yaml`
- `.yml`

For these files, Coryl will automatically read and write structured Python data.

## Registering Resources

### Generic Files and Directories

```python
app.register_file("notes", "data/notes.txt")
app.register_directory("exports", "build/exports")

app.write_content("notes", "Hello from Coryl")
print(app.content("notes"))
print(app.path("exports"))
```

You can also register them declaratively with `ResourceSpec`:

```python
from coryl import Coryl, ResourceSpec

app = Coryl(
    root=".",
    resources={
        "notes": ResourceSpec.file("data/notes.txt"),
        "exports": ResourceSpec.directory("build/exports"),
    },
)
```

### Config Files

Use `configs.add()` or `register_config()` when the file is a real application configuration file.

```python
settings = app.configs.add("settings", "config/settings.yaml")
```

Supported config formats:

- JSON
- TOML
- YAML

Config resources provide:

- `load()`
- `load_typed(model=None)`
- `save(data)`
- `save_typed(instance)`
- `get("dot.path", default=None)`
- `require("dot.path")`
- `update(...)`

Optional, lightweight config migrations are also available when local config files need to change shape between app versions. This is not a full migration framework: Coryl does not keep migration history, discover migrations automatically, or add database-like migration state. You register explicit Python functions on a config resource and call `migrate()` when you want to upgrade the file in place.

For layered config, use `configs.layered(...)`. This is intentionally smaller than Dynaconf or Hydra: Coryl gives you ordered file layers, deep-merged dictionaries, optional environment overrides, optional secrets, and explicit runtime overrides. There is no plugin system, implicit environment switching, or hidden discovery in this step.

Example:

```python
settings = app.configs.add("settings", "config/settings.yaml")

settings.save({"theme": "light", "language": "en"})
settings.update(language="it", timezone="Europe/Rome")

print(settings.load())
```

Optional file watching stays explicit and blocking. Coryl does not start background reload threads on its own.

```bash
pip install coryl[watch]
```

```python
def apply(config):
    print("reloaded", config)


for config in settings.watch_reload():
    apply(config)
```

If you prefer a tiny callback wrapper around the same explicit loop:

```python
settings.on_change(apply)
```

Optional typed config validation works with Pydantic v2 or `pydantic-settings`, but Coryl itself does not require either dependency unless you call the typed helpers.

```python
from pydantic import BaseModel


class SettingsModel(BaseModel):
    host: str
    port: int
    debug: bool = False


settings = app.configs.add(
    "settings",
    "config/settings.toml",
    schema=SettingsModel,
)

settings.save_typed(SettingsModel(host="localhost", port=5432, debug=True))
typed_settings = settings.load_typed()
print(typed_settings.port)
print(settings.require("host"))
```

Install the optional extra first:

```bash
pip install coryl[pydantic]
```

Config migration example:

```python
settings = app.configs.add("settings", "config/settings.toml", version=2)


@settings.migration(from_version=1, to_version=2)
def migrate_v1_to_v2(data):
    theme = data.pop("theme", "light")
    data["appearance"] = {"theme": theme}
    return data


settings.migrate()
print(settings.load()["version"])
```

The config file should contain a top-level integer `version`. Coryl applies registered migrations sequentially until it reaches the configured target version, then saves the migrated file atomically.

Layered config example:

```python
settings = app.configs.layered(
    "settings",
    files=[
        "config/defaults.toml",
        "config/local.toml",
        "config/production.toml",
    ],
    env_prefix="MYAPP",
    secrets="config/.secrets.toml",
    required=False,
)

settings.apply_overrides(["database.host=localhost", "debug=true"])

print(settings.get("database.host"))
print(settings.as_dict())
```

Merge order is explicit:

- defaults
- later files in `files=[...]`
- `secrets=...`
- environment variables like `MYAPP_DATABASE__HOST=localhost`
- runtime overrides from `override(...)` or `apply_overrides(...)`

Environment parsing is conservative by design:

- `true` and `false` become booleans
- integers and floats are parsed when unambiguous
- JSON arrays and objects such as `[1, 2]` or `{"region": "eu"}` are parsed
- everything else stays a string

The older `configs.layered("settings", "config/settings.yaml", secrets_dir=...)` form still works for the smaller single-file-plus-secret-directory case.

More detail lives in [docs/layered-config.md](docs/layered-config.md).

### Cache Directories

Use `caches.add()` or `register_cache()` for cache folders.

```python
cache = app.caches.add("http", ".cache/http")
```

Cache directories in Coryl are lightweight file caches for local artifacts, API responses, and generated runtime data. They are not intended to replace Redis or Memcached. By default, Coryl keeps this built-in cache file-oriented and simple.

Cache resources provide:

- `entry(...)`
- `file(...)`
- `directory(...)`
- `set(key, value, ttl=None)`
- `get(key, default=None)`
- `has(key)`
- `expire()`
- `remember(key_or_path, factory=None, content=None, ttl=None)`
- `remember_json(path, factory, ttl=None)`
- `remember_text(path, factory, ttl=None)`
- `load(...)`
- `delete(...)`
- `clear()`

Structured files such as `.json` keep Coryl's normal automatic data handling, text values stay text, and `set(..., bytes_value)` round-trips bytes through `get(...)`.

Example:

```python
cache = app.caches.add("http", ".cache/http")

user_data = cache.remember_json(
    "users/42.json",
    lambda: {"id": 42, "name": "Ada"},
    ttl=300,
)
state = cache.remember_text("tokens/state.txt", lambda: "ready", ttl=60)
cache.set("responses/blob.bin", b"abc123", ttl=120)

cached_user = cache.get("users/42.json")
cached_blob = cache.get("responses/blob.bin")

print(user_data)
print(state)
print(cached_user)
print(cached_blob)
```

If you want the low-level file-oriented behavior Coryl already had, `load(...)` still reads a cache file directly and `set(...)` eagerly writes a value immediately. The older multi-part `remember("dir", "file.json", content=...)` form is still accepted for compatibility.

If you need more robust persistent cache behavior, heavier cache workloads, or multi-process access, install the optional DiskCache backend and let Coryl manage the directory while DiskCache handles storage:

```bash
pip install coryl[diskcache]
```

```python
cache = app.caches.diskcache("api", ".cache/api")
# or: app.caches.add("api", ".cache/api", backend="diskcache")

cache.set("users:42", {"id": 42, "name": "Ada"}, ttl=300)
user = cache.get("users:42")
```

The built-in file cache is best when you want inspectable cache files and predictable path-based behavior. The DiskCache backend is a better fit for multi-process use or when you want a more capable persistent key-value cache without changing how Coryl manages resource roots.

### Asset Directories

Use `assets.add()` or `register_assets()` for filesystem-backed asset directories.

```python
assets = app.assets.add("ui", "assets")
```

Asset resources provide:

- `file(...)`
- `directory(...)`
- `require(...)`
- `files(pattern="**/*")`
- `glob(pattern)`

Example:

```python
assets = app.assets.add("ui", "assets")

logo = assets.require("images", "logo.svg")
icons = assets.directory("icons")
all_svgs = assets.files("**/*.svg")

print(logo.path)
print([path.name for path in all_svgs])
```

### Bundled Package Assets

Use `assets.from_package()` when assets are bundled inside an importable Python package and should be read through `importlib.resources`.

```python
assets = app.assets.from_package("templates", "myapp", "assets/templates")

email_template = assets.read_text("email.html")
logo_bytes = assets.read_bytes("images", "logo.bin")
```

Bundled package assets are different from filesystem `AssetGroup` instances:

- filesystem assets expose real `Path` objects and can be writable
- package assets are read-only by default
- package assets may not have a stable filesystem path when loaded from a wheel or zip file
- use `file(...).as_file()` to materialize a temporary path for one bundled file
- use `copy_to(...)` to bootstrap an entire bundled asset directory into a writable location

`assets.package(...)` is kept as a compatibility alias for `assets.from_package(...)`.

Example:

```python
assets = app.assets.from_package("bundled", "myapp", "assets")

template = assets.file("templates", "email.html")
with template.as_file() as path:
    print(path.read_text(encoding="utf-8"))

assets.copy_to("runtime/assets")
```

## Reading and Writing Files

### Generic Automatic Access

For generic file resources, `content()` and `write_content()` work automatically:

```python
app.register_file("data", "storage/data.json")

app.write_content("data", {"name": "Coryl", "version": 1})
print(app.content("data"))
```

If the file extension is structured, Coryl reads and writes structured data automatically. Otherwise it falls back to plain text, unless you write bytes explicitly.

### Safe Writes

On the default local filesystem, Coryl writes managed files safely by default. Text, bytes, and structured data writes go through an atomic replacement flow: Coryl writes a temporary file in the destination directory, flushes it, and then replaces the target file.

That means existing calls such as `resource.write_text(...)`, `resource.write_json(...)`, and `settings.save(...)` automatically use the safer behavior without changing your code.

When you opt into an `fsspec` backend, atomic replacement may not be available for that backend. In those cases Coryl falls back to a direct write instead of pretending the backend is atomic.

### Read-Only Resources

Any file, directory, config, cache, or asset resource can be marked with `readonly=True`.

```python
settings = app.register_config("settings", "config/settings.toml", readonly=True)
cache = app.register_cache("http_cache", ".cache/http", readonly=True)
assets = app.assets.from_package("ui", "myapp", "assets/ui")
```

Read operations still work normally. Mutating operations such as writes, deletes, clears, updates, and write-mode opens raise `CorylReadOnlyResourceError` with a clear message.

### Optional File Locking

If you want serialized access around read-modify-write flows, install the optional locking extra:

```bash
pip install coryl[lock]
```

Then use the resource-level context manager:

```python
with settings.lock():
    data = settings.load()
    settings.save(data)
```

Lock support currently applies to the default local filesystem resources. fsspec-backed resources may not expose a compatible cross-backend locking model in this first implementation.

`ConfigResource.update(..., lock=True)` uses the same lock flow for convenient config updates.

### Explicit File APIs

Every file resource also exposes explicit methods:

```python
resource = app.register_file("report", "reports/daily.txt")

resource.write_text("Daily report")
print(resource.read_text())
```

Structured resources expose:

```python
settings = app.configs.add("settings", "config/settings.toml")

settings.write_toml({"debug": True, "host": "localhost"})
print(settings.read_toml())
```

And YAML:

```python
settings = app.configs.add("settings", "config/settings.yaml")

settings.write_yaml({"theme": "dark"})
print(settings.read_yaml())
```

## Working with Child Paths

Directory resources can generate safe child resources:

```python
assets = app.assets.add("ui", "assets")

logo = assets.file("images", "logo.svg")
theme_dir = assets.directory("themes")
```

Coryl checks that generated child paths stay inside the parent directory.

## Manifest Support

Coryl can load resources from a manifest file.

Supported manifest formats:

- JSON
- TOML
- YAML

### Modern Schema (Preferred)

Modern manifests should declare `version = 2` and use a top-level `resources` mapping.

JSON example:

```json
{
  "version": 2,
  "resources": {
    "settings": {
      "path": "config/settings.toml",
      "kind": "file",
      "role": "config",
      "create": true,
      "format": "toml"
    },
    "http_cache": {
      "path": ".cache/http",
      "kind": "directory",
      "role": "cache",
      "backend": "diskcache"
    },
    "ui": {
      "path": "assets/ui",
      "kind": "directory",
      "role": "assets"
    }
  }
}
```

TOML example:

```toml
version = 2

[resources.settings]
path = "config/settings.toml"
kind = "file"
role = "config"
create = true
format = "toml"

[resources.http_cache]
path = ".cache/http"
kind = "directory"
role = "cache"
backend = "diskcache"

[resources.ui]
path = "assets/ui"
kind = "directory"
role = "assets"
```

YAML example:

```yaml
version: 2
resources:
  settings:
    path: config/settings.toml
    kind: file
    role: config
    create: true
    format: toml
  http_cache:
    path: .cache/http
    kind: directory
    role: cache
    backend: diskcache
  ui:
    path: assets/ui
    kind: directory
    role: assets
```

Supported optional resource fields:

- `create`
- `readonly`
- `required`
- `format`
- `schema`
- `backend`

For now, `schema` is stored as plain string metadata. Coryl does not require a JSON Schema dependency for manifest loading or validation.

Loading a manifest:

```python
app = Coryl(root=".", manifest_path="app.toml")

settings = app.configs.get("settings")
cache = app.caches.get("http_cache")
ui = app.assets.get("ui")
```

Reloading a manifest after editing it:

```python
app.load_config()
```

Note: `load_config()` is kept mainly for compatibility with the older design. It reloads the manifest, not an application config resource.

### Legacy Schema (Compatibility)

Older manifests using `paths.files` and `paths.directories` still load, but they are compatibility-only and the versioned `resources` schema above is preferred for new projects.

```yaml
paths:
  files:
    settings: config/settings.toml
  directories:
    cache: .cache/http
    ui: assets/ui
```

## Diagnostics CLI

The diagnostics CLI is an optional helper for projects that already use a Coryl manifest. It is not required to use the library from Python code.

The current CLI uses the standard library `argparse` module, so `pip install coryl` already includes it. `pip install coryl[cli]` is also supported if you prefer to keep optional tooling explicit in your project setup.

Examples:

```bash
coryl resources list --manifest app.toml --root .
coryl resources check --manifest app.toml --root .
coryl config show settings --manifest app.toml --root .
coryl cache clear http_cache --manifest app.toml --root .
coryl assets list ui --manifest app.toml --root .
```

Available commands:

- `coryl resources list` shows the resources loaded from the manifest, including role, kind, existence, and resolved path.
- `coryl resources check` reports missing or unsafe resources and exits with a non-zero status when problems are found.
- `coryl config show NAME` loads a managed config resource and prints its contents.
- `coryl cache clear NAME` clears a managed cache resource through Coryl's own cache API.
- `coryl assets list NAME` lists files inside a managed asset group.

By default the CLI prints a simple human-readable table. Add `--json` to any command for machine-readable output.

## Safety Model

Coryl applies a few important safety rules:

- All registration APIs, manifest entries, and `ResourceSpec` definitions resolve paths through the same root-confinement checks
- Managed paths are normalized before use and must stay inside the manager root
- Absolute paths are rejected by default, and traversal segments such as `..` are rejected even if they would normalize back inside the root
- Existing symlinks and junctions are handled conservatively; Coryl rejects managed paths that would escape the allowed root or a directory resource through them
- Child paths created from managed directories must stay inside those directories
- Config resources must be structured files
- Cache and asset resources must be directories

This makes Coryl useful for applications that want predictable, centralized resource management without scattering `Path(...)` logic everywhere.

## API Overview

### Manager

Main entry points:

- `Coryl(root, resources=None, manifest_path=None, create_missing=True)`
- `Coryl(root, resources=None, manifest_path=None, create_missing=True, filesystem="fsspec", protocol=...)`
- `Coryl.with_fs(root, protocol=None, resources=None, manifest_path=None, create_missing=True)`
- `Coryl.for_app(app_name, app_author=None, version=None, roaming=False, multipath=False, ensure=True, create_missing=True)`
- `register_file(name, path, ...)`
- `register_directory(name, path, ...)`
- `register_config(name, path, ...)`
- `register_config(name, path, ..., version=None)`
- `register_layered_config(name, path=None, ..., files=None, env_prefix=None, secrets=None, secrets_dir=None, version=None)`
- `register_cache(name, path, ...)`
- `register_data(name, path, ...)`
- `register_log(name, path, ...)`
- `register_assets(name, path, ...)`
- `register_package_assets(name, package, relative_path=".", ...)`
- `resource(name)`
- `file(name)`
- `directory(name)`
- `config_resource(name="config")`
- `cache_resource(name)`
- `asset_group(name)`
- `path(name)`
- `content(name, default=...)`
- `write_content(name, value)`
- `load_manifest(path)`
- `load_config()`
- `audit_paths()`

Namespaces:

- `app.configs`
- `app.caches`
- `app.data`
- `app.logs`
- `app.assets`
- `app.assets.from_package(name, package, path="")`

### Generic Resource

Useful methods:

- `ensure()`
- `exists()`
- `lock(timeout=None)`
- `read_text()`
- `write_text(text, atomic=True)`
- `read_bytes()`
- `write_bytes(data, atomic=True)`
- `read_data()`
- `write_data(data, atomic=True)`
- `read_json()`
- `write_json(data, atomic=True)`
- `read_toml()`
- `write_toml(data, atomic=True)`
- `read_yaml()`
- `write_yaml(data, atomic=True)`
- `content()`
- `write(value)`
- `watch(...)`

### ConfigResource

Additional helpers:

- `load()`
- `load_typed(model=None)`
- `save(data, atomic=True)`
- `save_typed(instance, atomic=True)`
- `get(key_path, default=None)`
- `require(key_path, default=...)`
- `migration(from_version=..., to_version=...)`
- `migrate()`
- `update(..., lock=False)`
- `watch_reload(...)`
- `on_change(callback, ...)`
- `load_base()` on layered configs

Layered configs additionally provide:

- `as_dict()`
- `reload()`
- `override(mapping)`
- `apply_overrides(["key=value"])`

### CacheResource

Additional helpers:

- `entry(...)`
- `file(...)`
- `directory(...)`
- `set(key, value, ttl=None)`
- `get(key, default=None)`
- `has(key)`
- `expire()`
- `remember(key_or_path, factory=None, content=None, ttl=None)`
- `remember_json(path, factory, ttl=None)`
- `remember_text(path, factory, ttl=None)`
- `load(...)`
- `delete(...)`
- `clear()`

### DiskCacheResource

Additional helpers:

- `set(key, value, ttl=None)`
- `get(key, default=None)`
- `has(key)`
- `delete(key)`
- `clear()`
- `expire()`
- `remember(key_or_path, factory=None, content=None, ttl=None)`
- `remember_json(path, factory, ttl=None)`
- `remember_text(path, factory, ttl=None)`
- `memoize(ttl=None)`
- `raw`

### AssetGroup

Additional helpers:

- `file(...)`
- `directory(...)`
- `require(...)`
- `files(pattern="**/*")`
- `glob(pattern)`

### PackageAssetGroup

Additional helpers:

- `read_text(...)`
- `read_bytes(...)`
- `file(...)`
- `require(...)`
- `exists(...)`
- `files(pattern="**/*")`
- `copy_to(target_directory, overwrite=False)`

## Examples

### Example 1: CLI Tool Configuration

```python
from coryl import Coryl

app = Coryl(root=".")
settings = app.configs.add("settings", "config/cli.toml")

if not settings.path.read_text(encoding="utf-8").strip():
    settings.save({"theme": "dark", "verbose": False})

config = settings.load()
print(config["theme"])
```

### Example 2: API Response Cache

```python
from coryl import Coryl

app = Coryl(root=".")
cache = app.caches.add("api", ".cache/api")

user = cache.remember_json(
    "users/42.json",
    lambda: {"id": 42, "name": "Ada"},
    ttl=300,
)
print(user["name"])
```

### Example 3: Desktop App Assets

```python
from coryl import Coryl

app = Coryl(root=".")
assets = app.assets.add("desktop", "assets")

icon = assets.require("icons", "app.png")
templates = assets.directory("templates")

print(icon.path)
print(templates.path)
```

### Example 4: Declarative Startup

```python
from coryl import Coryl, ResourceSpec

app = Coryl(
    root=".",
    resources={
        "settings": ResourceSpec.config("config/settings.yaml"),
        "cache": ResourceSpec.cache(".cache/app"),
        "assets": ResourceSpec.assets("assets"),
        "notes": ResourceSpec.file("data/notes.txt"),
    },
)

app.configs.get("settings").save({"language": "en"})
app.caches.get("cache").set("session.json", {"token": "abc"}, ttl=300)
print(app.assets.get("assets").files("**/*"))
```

### Example 5: Docker or Kubernetes Config

```python
from coryl import Coryl

app = Coryl(root=".")

settings = app.configs.layered(
    "settings",
    files=["config/settings.yaml"],
    readonly=True,
    secrets_dir="/run/secrets",
)

certs = app.register_assets("certs", "mounted/certs", readonly=True)

print(settings.load())
print(certs.files("*.crt"))
```

This pattern works well with mounted config files under your app root, Docker secrets, Kubernetes secrets, and read-only volumes.

## Compatibility Notes

Coryl still exposes a few compatibility helpers inspired by the older `FileManager` design:

- `root_folder_path`
- `config_file_path`
- `config`
- `load_config()`
- `content()`
- `write_content()`
- dynamic attributes such as `settings_file_path` and `cache_directory_path`

## Important Note About `config`

The `config` property on `ResourceManager` is reserved for the loaded manifest content.

For application configuration files, prefer:

- `app.configs.add(...)`
- `app.configs.get(...)`
- `app.config_resource(...)`

This avoids confusion between:

- the manager manifest
- your actual application settings files
