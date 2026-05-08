# Coryl

Coryl is a lightweight Python application resource manager for configs, caches, assets, and files under safe roots.

## Quick Start

```bash
pip install coryl
```

```python
from coryl import Coryl

app = Coryl(root=".")

settings = app.configs.add("settings", "config/settings.toml")
cache = app.caches.add("http", ".cache/http")
assets = app.assets.add("ui", "assets/ui")

settings.save(
    {
        "app_name": "Coryl Demo",
        "debug": True,
    }
)

config = settings.load()
user = cache.remember_json(
    "users/42.json",
    lambda: {"id": 42, "name": "Ada"},
    ttl=300,
)
logo = assets.file("images", "logo.svg", create=False)

print(config["app_name"])
print(user["name"])
print(logo.path)
```

## Why Coryl

- One resource layer for files, configs, caches, and assets.
- Safe path resolution relative to one root.
- Structured file helpers for JSON and TOML out of the box.
- Clear `configs`, `caches`, and `assets` namespaces.
- Optional integrations stay opt-in.

## Core Concepts

### Root

Every managed path is resolved relative to one root. The default path stays local and simple with `Coryl(root=".")`.

### Resources

Resources are named files or directories registered under the root with helpers such as `register_file(...)` and `register_directory(...)`.

### Configs

Config resources are structured files with `load()`, `save()`, `get()`, and `update()` helpers.

### Caches

Cache resources are managed directories for inspectable cache files through helpers such as `remember_json(...)`, `remember_text(...)`, `get(...)`, and `set(...)`.

### Assets

Asset resources are managed directories for safe file lookups through helpers such as `file(...)`, `directory(...)`, and `require(...)`.

Bundled package assets are read through `importlib.resources`, so the same calls work from a source tree, a regular install, or a zipped import:

```python
import importlib
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

from coryl import Coryl

with TemporaryDirectory() as temp_dir:
    root = Path(temp_dir)
    package_name = "coryl_readme_pkg"
    package_root = root / package_name
    templates_root = package_root / "assets" / "templates"
    templates_root.mkdir(parents=True, exist_ok=True)
    (package_root / "__init__.py").write_text("", encoding="utf-8")
    (templates_root / "email.html").write_text(
        "<html>Hello from Coryl</html>",
        encoding="utf-8",
    )

    sys.path.insert(0, str(root))
    importlib.invalidate_caches()
    sys.modules.pop(package_name, None)
    try:
        app = Coryl(root=root)
        assets = app.assets.from_package("templates", package_name, path="assets/templates")
        print(assets.read_text("email.html"))
        with assets.file("email.html").as_file() as path:
            print(path.name)
    finally:
        sys.modules.pop(package_name, None)
        importlib.invalidate_caches()
        sys.path.remove(str(root))
```

`files(pattern=...)` also works for zipped packages because Coryl walks package resources through `importlib.resources`. The returned values are package resource handles, not stable paths, so use `read_text()`, `read_bytes()`, `file(...).as_file()`, or `copy_to()` when you need on-disk access.

### Manifests

Manifests let you declare resources in JSON, TOML, or YAML and load them through one file. JSON and TOML work in the core install. YAML support requires `pip install coryl[yaml]`.

## Safety Model

- Root confinement: registered paths must stay inside the managed root.
- Child path confinement: child files and directories created from managed directories must stay inside the parent.
- Read-only resources: files, configs, caches, and assets can be marked `readonly=True`.
- Atomic writes: the default local filesystem uses atomic replace writes for text, bytes, and structured data.

## Optional Features

Core install:

```bash
pip install coryl
```

- `coryl[platform]` for OS app directories with `Coryl.for_app(...)`.
- `coryl[pydantic]` for typed config loading and saving.
- `coryl[diskcache]` for the `diskcache` cache backend.
- `coryl[watch]` for blocking watch and reload helpers.
- `coryl[fsspec]` for conservative fsspec-backed local or remote filesystem roots.
- `coryl[lock]` for inter-process file locks.
- `coryl[cli]` for diagnostics commands.

Additional format support:

- `coryl[yaml]` for YAML config and manifest files.

Everything installed:

```bash
pip install coryl[all]
```

Deeper docs:

- [docs/layered-config.md](docs/layered-config.md)
- [docs/ROADMAP_IMPLEMENTATION.md](docs/ROADMAP_IMPLEMENTATION.md)

## Examples

- Simple local app: [examples/simple_local_app.py](examples/simple_local_app.py)
- CLI tool config: [examples/cli_tool_config.py](examples/cli_tool_config.py)
- API cache: [examples/api_cache.py](examples/api_cache.py)
- Package assets: [examples/package_assets.py](examples/package_assets.py)
- Typed config: [examples/typed_config.py](examples/typed_config.py)
- Layered config: [examples/layered_config.py](examples/layered_config.py)

## Compatibility Notes

- The default `Coryl(root=...)` path handling stays local and pathlib-backed. fsspec support is only enabled when you opt into `Coryl.with_fs(...)` or `Coryl(..., filesystem="fsspec")`.
- fsspec support is intentionally conservative: basic file and directory registration, text and bytes I/O, structured JSON and TOML helpers, optional YAML helpers, directory globbing, and the built-in file-backed cache helpers work on supported backends such as `memory://`.
- Atomic replace guarantees remain local-only. fsspec-backed resources fall back to regular writes when `atomic=True`.
- `open()`, `lock()`, and `watch()` remain local-only helpers.
- The `diskcache` backend and layered config workflows remain local-only.
- Legacy `FileManager`-style helpers are still available for older code.
- `load_config()` reloads the manifest, not an application settings resource.
- `app.config` is reserved for loaded manifest content.
