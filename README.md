# Coryl

A lightweight Python application resource manager for configs, caches, assets, and files under safe roots.

## Why Coryl?

Many Python applications eventually need the same small set of file concerns:

- a config file or two
- a local cache
- some bundled assets
- maybe runtime data and logs

The hard part is usually not file I/O itself. The hard part is keeping paths predictable, avoiding accidental path traversal, and not letting app-specific conventions spread across the codebase.

Coryl keeps that layer small. The default path is intentionally simple: `Coryl(root=".")` plus a few focused namespaces such as `configs`, `caches`, and `assets`. When you need more, optional extras add typed config validation, layered config, file watching, `diskcache`, `fsspec`, platform-specific app directories, and file locks without turning the core package into a framework.

## Installation

Core install:

```bash
pip install coryl
```

The core install includes:

- the default local filesystem manager
- JSON and TOML structured I/O
- the built-in file-backed cache
- filesystem and package asset helpers
- the `coryl` diagnostics CLI

Optional extras:

| Extra | Install | What it enables | Notes |
| --- | --- | --- | --- |
| `lock` | `pip install coryl[lock]` | `Resource.lock()` | Local filesystem only. |
| `diskcache` | `pip install coryl[diskcache]` | `app.caches.diskcache(...)` and `backend="diskcache"` | Local filesystem only. |
| `fsspec` | `pip install coryl[fsspec]` | `Coryl.with_fs(...)` and `filesystem="fsspec"` | Opt-in, conservative support. |
| `platform` | `pip install coryl[platform]` | `Coryl.for_app(...)` | Uses `platformdirs` for config/cache/data/log roots. |
| `pydantic` | `pip install coryl[pydantic]` | `load_typed()` and `save_typed()` | Expects a Pydantic v2-style interface. |
| `watch` | `pip install coryl[watch]` | `watch()`, `watch_reload()`, `on_change()` | Local filesystem only and blocking. |
| `yaml` | `pip install coryl[yaml]` | `read_yaml()`, `write_yaml()`, YAML manifests, and YAML layered-config files | Loaded lazily when you touch YAML files. |
| `cli` | `pip install coryl[cli]` | No extra dependencies today | The CLI already ships with `pip install coryl`. |
| `all` | `pip install coryl[all]` | Full optional feature set | Includes the declared extras, including YAML support. |

Missing optional dependencies fail lazily. Coryl imports them only when you use the
related feature, then raises `CorylOptionalDependencyError` with the matching
`pip install coryl[...]` hint.

More detail:

- [Optional extras](docs/optional-extras.md)
- [Limitations](docs/limitations.md)

## Quick Start

```python
from coryl import Coryl

app = Coryl(root=".")

settings = app.configs.add("settings", "config/settings.toml")
cache = app.caches.add("http", ".cache/http")
assets = app.assets.add("ui", "assets/ui")

settings.save({"app_name": "Coryl Demo", "debug": True})
loaded_settings = settings.load()

user = cache.remember_json(
    "users/42.json",
    lambda: {"id": 42, "name": "Ada"},
    ttl=300,
)

logo = assets.file("images", "logo.svg", create=True)
logo.write_text("<svg />")
same_logo = assets.require("images", "logo.svg")

print(loaded_settings["app_name"])
print(user["name"])
print(same_logo.path)
```

## Core Concepts

- `root`: the managed base path. Local resources are resolved under this root and must stay inside it.
- `resources`: named files or directories you register with `register_file(...)`, `register_directory(...)`, or one of the typed namespaces.
- `configs`: structured file resources exposed through `app.configs`.
- `caches`: managed cache directories exposed through `app.caches`.
- `assets`: safe asset directories exposed through `app.assets`.
- `data` / `logs`: plain resources exposed through `app.data` and `app.logs`.
- `manifests`: JSON, TOML, or YAML declarations that register multiple resources at startup.

Most applications can stay inside one root. If you later need platform-specific config/cache/data/log routing, `Coryl.for_app(...)` adds that without changing the basic model.

## Safety Model

- Root confinement: registered paths must stay inside the manager root or the named root chosen by `Coryl.for_app(...)`.
- Child path confinement: child helpers such as `assets.file(...)`, `cache.file(...)`, and `resource.joinpath(...)` must stay inside their parent resource.
- Traversal rejection: Coryl rejects path traversal segments such as `..`, even when the normalized path would appear to land back inside the root.
- Symlink behavior: local directory symlinks or junctions that would escape the allowed root are rejected during registration and during child lookups.
- Read-only resources: files, configs, caches, and assets can be marked `readonly=True`; reads still work, writes do not.
- Atomic writes: local `write_text()`, `write_bytes()`, `write_json()`, `write_toml()`, `write_yaml()`, and config `save()` operations use atomic replacement by default.
- fsspec limitations: Coryl's fsspec backend does not support local-only helpers such as `open()`, `lock()`, `watch()`, layered config, or the `diskcache` backend, and fsspec writes fall back to regular writes even when `atomic=True`.

## Files and Structured Data

Coryl keeps generic file I/O small and explicit:

| Type | Read | Write | Notes |
| --- | --- | --- | --- |
| Text | `read_text()` | `write_text()` | Uses the resource encoding, default `utf-8`. |
| Bytes | `read_bytes()` | `write_bytes()` | Raw binary I/O. |
| JSON | `read_json()` | `write_json()` | Core install. |
| TOML | `read_toml()` | `write_toml()` | Core install. |
| YAML | `read_yaml()` | `write_yaml()` | Requires `coryl[yaml]`. |

`read_data()` and `write_data()` infer the structured format from the file extension. `content()` and `write()` provide one higher-level layer that auto-detects structured formats, text, and bytes.

```python
from coryl import Coryl

app = Coryl(root=".")

notes = app.register_file("notes", "data/notes.txt")
notes.write_text("hello")

blob = app.register_file("blob", "data/blob.bin")
blob.write_bytes(b"\x00\x01coryl")

state = app.register_file("state", "data/state.json")
state.write_json({"count": 1})

settings = app.register_file("settings", "config/app.toml")
settings.write_toml({"debug": True, "theme": "dark"})
```

The sections below cover optional or more advanced workflows. Core usage stays intentionally smaller than the full surface area.

## Configs

### Basic config

`ConfigResource` adds structured config helpers on top of a normal file resource.

```python
from coryl import Coryl

app = Coryl(root=".")
settings = app.configs.add("settings", "config/settings.toml")

settings.save(
    {
        "debug": False,
        "database": {"host": "localhost", "ports": [5432, 5433]},
    }
)

print(settings.get("database.host"))
print(settings.get("database.ports.1"))

updated = settings.update({"debug": True}, timezone="Europe/Rome")
print(updated["timezone"])
```

### Typed config

Requires `coryl[pydantic]`.

```python
from importlib.util import find_spec

if find_spec("pydantic") is not None:
    from pydantic import BaseModel

    from coryl import Coryl

    class SettingsModel(BaseModel):
        host: str
        port: int
        debug: bool = False

    app = Coryl(root=".")
    settings = app.configs.add(
        "settings", "config/settings.toml", schema=SettingsModel
    )

    settings.save_typed(SettingsModel(host="localhost", port=5432, debug=True))
    typed_settings = settings.load_typed()

    print(typed_settings.host)
    print(typed_settings.port)
```

### Layered config

Requires the default local filesystem. This is a separate resource type exposed through `app.configs.layered(...)`.

```python
import os
from pathlib import Path

from coryl import Coryl

Path("config").mkdir(exist_ok=True)
Path("config/defaults.toml").write_text(
    'debug = false\n[database]\nhost = "db"\n',
    encoding="utf-8",
)
Path("config/local.toml").write_text('theme = "local"\n', encoding="utf-8")

previous_host = os.environ.get("MYAPP_DATABASE__HOST")
os.environ["MYAPP_DATABASE__HOST"] = "env-db"
try:
    app = Coryl(root=".")
    settings = app.configs.layered(
        "settings",
        files=["config/defaults.toml", "config/local.toml"],
        env_prefix="MYAPP",
    )

    settings.override({"debug": True})
    print(settings.as_dict())
finally:
    if previous_host is None:
        os.environ.pop("MYAPP_DATABASE__HOST", None)
    else:
        os.environ["MYAPP_DATABASE__HOST"] = previous_host
```

### Env overrides

With `env_prefix="MYAPP"`, environment variables map onto dotted config keys:

- `MYAPP_DEBUG=true` -> `debug = True`
- `MYAPP_DATABASE__HOST=localhost` -> `database.host = "localhost"`
- `MYAPP_DATABASE__PORT=5432` -> `database.port = 5432`

Parsing is conservative. Booleans, integers, floats, JSON-like arrays, and JSON-like objects are converted when possible; otherwise values stay as strings.

### Secrets

Layered config can merge secrets from:

- `secrets="config/.secrets.toml"` for one structured secrets file
- `secrets_dir="run/secrets"` for a directory where each filename becomes a top-level key

Use `required=True` when missing layers or secrets inputs should fail instead of being skipped.

### Migrations

Versioned config migrations stay local to one config resource.

```python
from coryl import Coryl

app = Coryl(root=".")
settings = app.configs.add("settings", "config/settings.toml", version=2)
settings.save({"version": 1, "theme": "light"})


@settings.migration(from_version=1, to_version=2)
def migrate_to_v2(document: dict[str, object]) -> dict[str, object]:
    document["appearance"] = {"theme": document.pop("theme")}
    return document


print(settings.migrate())
```

### `watch_reload()`

Requires `coryl[watch]` and the default local filesystem.

```text
# Conceptual: this blocks and yields whenever the config changes on disk.
for updated in settings.watch_reload():
    print(updated)
```

`on_change(callback)` is the callback-oriented equivalent.

## Caches

### Built-in file cache

The default cache is a managed directory with inspectable files on disk.

```python
from coryl import Coryl

app = Coryl(root=".")
cache = app.caches.add("http", ".cache/http")

cache.set("tokens/state.txt", "ready", ttl=60)
user = cache.remember_json(
    "users/42.json",
    lambda: {"id": 42, "name": "Ada"},
    ttl=300,
)

print(cache.get("tokens/state.txt"))
print(user["name"])
```

TTL metadata for the built-in cache is stored in a reserved file named `.coryl-cache-index.json` inside the cache directory.

### TTL and remember helpers

- `set(key, value, ttl=...)` stores a value with an optional expiration
- `get(key, default=...)` returns the value or the default
- `has(key)` checks existence and expiration
- `expire()` removes expired entries
- `remember(...)`, `remember_json(...)`, and `remember_text(...)` compute and store a value only when needed

### DiskCache backend

Requires `coryl[diskcache]` and the default local filesystem.

```python
from importlib.util import find_spec

if find_spec("diskcache") is not None:
    from coryl import Coryl

    app = Coryl(root=".")
    cache = app.caches.diskcache("api", ".cache/api")

    @cache.memoize(ttl=60)
    def load_user(user_id: int) -> dict[str, object]:
        return {"id": user_id}

    print(load_user(42))
```

You can also register it with `app.caches.add(..., backend="diskcache")`.

### Which cache should you use?

- Use the built-in cache when you want inspectable files, path-based entries, or fsspec support.
- Use the `diskcache` backend when you want opaque Python object caching and decorator-style memoization on one local machine.

## Assets

### Filesystem assets

`AssetGroup` is for safe file and directory lookups under a managed asset root.

```python
from coryl import Coryl

app = Coryl(root=".")
assets = app.assets.add("ui", "assets/ui")

logo = assets.file("images", "logo.svg", create=True)
logo.write_text("<svg />")

print(assets.require("images", "logo.svg").path)
print(assets.files("**/*"))
```

Use `file(...)`, `directory(...)`, and `require(...)` for lookups. Use `files(pattern=...)` when you want files only, and `glob(pattern)` when you want both files and directories.

### Package assets

Package-backed assets are read-only and use `importlib.resources`, so they work from a source tree, a normal install, or a zipped import.

```text
# Conceptual: assumes myapp.assets_pkg is an importable package with bundled files.
from coryl import Coryl

app = Coryl(root=".")
bundled = app.assets.from_package("bundled", "myapp.assets_pkg", "assets")

print(bundled.read_text("templates", "email.html"))
```

### `copy_to()` bootstrap

Package assets do not promise a stable on-disk `path`. When you need real files on disk, use `as_file()` for one file or `copy_to(...)` for a whole tree.

```text
# Conceptual: bootstrap bundled assets into a writable directory.
target_root = bundled.copy_to("bootstrap-assets", overwrite=True)
print(target_root)
```

## Installed Apps

Requires `coryl[platform]`.

`Coryl.for_app(...)` builds a manager around `platformdirs` and routes resource types to the expected OS-specific roots:

- `configs` -> config root
- `caches` -> cache root
- `data` -> data root
- `logs` -> log root
- `assets` -> data root

```python
from importlib.util import find_spec

if find_spec("platformdirs") is not None:
    from coryl import Coryl

    app = Coryl.for_app("MyTool", app_author="Acme", version="1.2.3", ensure=True)

    settings = app.configs.add("settings", "settings.toml")
    cache = app.caches.add("http", "http")
    state = app.data.add("state", "state.json")
    log = app.logs.add("main", "app.log")
    assets = app.assets.add("ui", "assets/ui")
```

Use `ensure=True` when you want the platform roots created immediately. With `ensure=False`, roots are created as resource creation requires them.

## Manifests

Version 2 is the preferred manifest schema. It carries explicit `path`, `kind`, `role`, and optional metadata such as `readonly`, `required`, `format`, `schema`, and `backend`.

Load a manifest at startup:

```python
from pathlib import Path

from coryl import Coryl

Path("app.toml").write_text(
    'version = 2\n\n[resources.settings]\npath = "config/settings.toml"\nkind = "file"\nrole = "config"\ncreate = false\n',
    encoding="utf-8",
)

app = Coryl(root=".", manifest_path="app.toml", create_missing=False)
print(sorted(app.resources))
```

### TOML v2

```toml
version = 2

[resources.settings]
path = "config/settings.toml"
kind = "file"
role = "config"
create = false

[resources.http_cache]
path = ".cache/http"
kind = "directory"
role = "cache"
create = false
```

### JSON v2

```json
{
  "version": 2,
  "resources": {
    "settings": {
      "path": "config/settings.toml",
      "kind": "file",
      "role": "config",
      "create": false
    },
    "ui": {
      "path": "assets/ui",
      "kind": "directory",
      "role": "assets",
      "create": false
    }
  }
}
```

### YAML v2

Requires `coryl[yaml]`.

```yaml
version: 2
resources:
  settings:
    path: config/settings.toml
    kind: file
    role: config
    create: false
  ui:
    path: assets/ui
    kind: directory
    role: assets
    create: false
```

### Legacy schema compatibility

Legacy manifests still load for compatibility:

```json
{
  "paths": {
    "files": {
      "settings": "config/settings.toml"
    },
    "directories": {
      "http_cache": ".cache/http",
      "ui": "assets/ui"
    }
  }
}
```

Use v2 for new work. The legacy schema only describes file and directory paths; it does not carry typed resource roles such as `config`, `cache`, or `assets`.

## Diagnostics CLI

The CLI is meant for inspection and maintenance, not for defining your application architecture.

Commands:

- `coryl resources list --manifest app.toml --root .`
- `coryl resources check --manifest app.toml --root .`
- `coryl config show settings --manifest app.toml --root .`
- `coryl cache clear http_cache --manifest app.toml --root .`
- `coryl assets list ui --manifest app.toml --root .`

Use `--json` on every command when you want machine-readable output.

Behavior notes:

- `resources list` loads the manifest and prints resource role, kind, existence, safety, and path.
- `resources check` returns exit code `1` when any resource is missing or unsafe.
- `config show` prints one config resource from the manifest.
- `cache clear` clears one cache resource from the manifest.
- `assets list` lists files from filesystem assets or package assets.

## Advanced Filesystems

Requires `coryl[fsspec]`.

`fsspec` support is opt-in:

- `Coryl.with_fs(root, protocol=...)`
- `Coryl(root=..., filesystem="fsspec", protocol=...)`

Memory filesystem example:

```python
from importlib.util import find_spec

if find_spec("fsspec") is not None:
    from coryl import Coryl

    app = Coryl.with_fs("memory://demo", protocol="memory")
    settings = app.configs.add("settings", "config/settings.json")
    cache = app.caches.add("api", ".cache/api")

    settings.save({"theme": "light"})
    user = cache.remember_json("users/42.json", lambda: {"id": 42})

    print(settings.load())
    print(user)
```

Current limitations:

- local-only helpers such as `open()`, `lock()`, and `watch()` do not work
- layered config is local-only
- the `diskcache` backend is local-only
- local atomic replace semantics are not available; writes fall back to regular writes

See [Limitations](docs/limitations.md) for the current boundary.

## API Overview

The public surface is small enough to skim and broad enough that the full reference is still useful. See [API reference](docs/api-reference.md) for signatures and behavior details.

The main pieces are:

- `Coryl` / `ResourceManager`: root management, registration, manifests, and lookups
- `Resource`: generic file or directory helpers
- `ConfigResource`: structured config load/save/get/update plus migrations, typed config, and watch helpers
- `LayeredConfigResource`: local layered config with files, environment overrides, secrets, and runtime overrides
- `CacheResource` / `DiskCacheResource`: built-in file-backed caching or optional `diskcache`
- `AssetGroup` / `PackageAssetGroup`: filesystem assets or package-backed assets
- `ResourceSpec`: declarative resource definitions for registration and manifests

## Examples

See [examples/](examples/) for runnable scripts validated by the test suite.

Optional examples such as `typed_config.py`, `cache_diskcache.py`, and
`fsspec_memory.py` still run from a fresh checkout. When the extra is not installed,
they print a small JSON payload with `available: false` and `skipped: true` instead of
failing.

- [examples/simple_local_app.py](examples/simple_local_app.py): `Coryl(root=...)` with TOML config, JSON config, cache, and asset lookup
- [examples/cli_tool_config.py](examples/cli_tool_config.py): create a default config, update it, and print a value
- [examples/api_cache.py](examples/api_cache.py): fake API caching with `remember_json(..., ttl=...)`
- [examples/desktop_app_assets.py](examples/desktop_app_assets.py): filesystem assets with `require()`, `files()`, and `glob()`
- [examples/manifest_startup.py](examples/manifest_startup.py): write `app.toml`, load it, use configs/caches/assets, and inspect `audit_paths()`
- [examples/package_assets.py](examples/package_assets.py): package assets with `read_text()`, `read_bytes()`, and `copy_to()`
- [examples/typed_config.py](examples/typed_config.py): typed config loading with Pydantic when available
- [examples/layered_config.py](examples/layered_config.py): defaults, local overrides, environment overrides, and runtime overrides
- [examples/cache_diskcache.py](examples/cache_diskcache.py): optional `diskcache` cache backend
- [examples/fsspec_memory.py](examples/fsspec_memory.py): optional `fsspec` memory filesystem backend
- [examples/diagnostics_cli.py](examples/diagnostics_cli.py): `resources list`, `resources check`, and `config show`

## Compatibility Notes

- Legacy `FileManager`-style path helpers still exist, including `root_folder_path`, `config_file_path`, and dynamic aliases such as `<name>_file_path` and `<name>_directory_path` when the resource kind matches.
- `app.config` is reserved for loaded manifest content. It is not a shortcut to an application settings resource.
- `load_config()` reloads the current manifest file and updates `app.config`.

## Design Principles

- Simple by default: the core path is `Coryl(root=".")` plus a few focused namespaces.
- Safe by default: Coryl rejects unsafe paths instead of trying to recover from them.
- Optional integrations: typed configs, platformdirs, watching, locks, `diskcache`, `fsspec`, and YAML stay opt-in.
- No framework lock-in: Coryl manages application resources; it does not impose a larger app structure.
- Lazy optional imports: optional dependencies are only imported when you actually use the related feature.

## License

MIT. See [LICENSE](LICENSE).
