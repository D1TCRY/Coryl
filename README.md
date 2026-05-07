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
- Generic file and directory management when you do not need special behavior
- Modern manifest loading from JSON, TOML, or YAML
- Compatibility helpers for older `FileManager`-style code

## Installation

```bash
pip install coryl
```

Optional file locking support:

```bash
pip install coryl[lock]
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

http_cache.remember("responses", "users.json", content={"count": 42})
logo = ui_assets.file("images", "logo.svg", create=False)

print(settings.load())
print(http_cache.load("responses", "users.json"))
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
- `save(data)`
- `update(...)`

Example:

```python
settings = app.configs.add("settings", "config/settings.yaml")

settings.save({"theme": "light", "language": "en"})
settings.update(language="it", timezone="Europe/Rome")

print(settings.load())
```

### Cache Directories

Use `caches.add()` or `register_cache()` for cache folders.

```python
cache = app.caches.add("http", ".cache/http")
```

Cache resources provide:

- `entry(...)`
- `file(...)`
- `directory(...)`
- `remember(..., content=...)`
- `load(...)`
- `delete(...)`
- `clear()`

Example:

```python
cache = app.caches.add("http", ".cache/http")

cache.remember("users", "42.json", content={"id": 42, "name": "Ada"})
cache.remember("tokens", "state.txt", content="ready")

user_data = cache.load("users", "42.json")
state = cache.load("tokens", "state.txt")

print(user_data)
print(state)
```

### Asset Directories

Use `assets.add()` or `register_assets()` for static or bundled application assets.

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

Coryl writes managed files safely by default. Text, bytes, and structured data writes go through an atomic replacement flow: Coryl writes a temporary file in the destination directory, flushes it, and then replaces the target file.

That means existing calls such as `resource.write_text(...)`, `resource.write_json(...)`, and `settings.save(...)` automatically use the safer behavior without changing your code.

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

Manifests use a single modern schema with a top-level `resources` mapping.

JSON example:

```json
{
  "resources": {
    "settings": {
      "path": "config/settings.toml",
      "kind": "file",
      "role": "config"
    },
    "http_cache": {
      "path": ".cache/http",
      "kind": "directory",
      "role": "cache"
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
[resources.settings]
path = "config/settings.toml"
kind = "file"
role = "config"

[resources.http_cache]
path = ".cache/http"
kind = "directory"
role = "cache"

[resources.ui]
path = "assets/ui"
kind = "directory"
role = "assets"
```

YAML example:

```yaml
resources:
  settings:
    path: config/settings.yaml
    kind: file
    role: config
  http_cache:
    path: .cache/http
    kind: directory
    role: cache
  ui:
    path: assets/ui
    kind: directory
    role: assets
```

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
- `register_file(name, path, ...)`
- `register_directory(name, path, ...)`
- `register_config(name, path, ...)`
- `register_cache(name, path, ...)`
- `register_assets(name, path, ...)`
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

Namespaces:

- `app.configs`
- `app.caches`
- `app.assets`

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

### ConfigResource

Additional helpers:

- `load()`
- `save(data, atomic=True)`
- `update(..., lock=False)`

### CacheResource

Additional helpers:

- `entry(...)`
- `file(...)`
- `directory(...)`
- `remember(..., content=...)`
- `load(...)`
- `delete(...)`
- `clear()`

### AssetGroup

Additional helpers:

- `file(...)`
- `directory(...)`
- `require(...)`
- `files(pattern="**/*")`
- `glob(pattern)`

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

cache.remember("users", "42.json", content={"id": 42, "name": "Ada"})
user = cache.load("users", "42.json")
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
app.caches.get("cache").remember("session.json", content={"token": "abc"})
print(app.assets.get("assets").files("**/*"))
```

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
