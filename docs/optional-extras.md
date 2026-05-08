# Optional Extras

This page reflects the extras declared in `pyproject.toml`.

## Core Install

Install:

```bash
pip install coryl
```

What you get:

- The default local filesystem manager: `Coryl(root=...)`
- `Resource`, `ConfigResource`, `CacheResource`, `AssetGroup`, data resources, and log
  resources
- JSON and TOML structured I/O
- File-backed cache helpers
- Package asset helpers
- The `coryl` console script

What is not included:

- `platformdirs`
- `pydantic`
- `diskcache`
- `watchfiles`
- `fsspec`
- `filelock`
- `PyYAML`

## `lock`

Install:

```bash
pip install coryl[lock]
```

What it enables:

- `Resource.lock(timeout=None)`

Notes:

- Locking is local-filesystem-only.
- Coryl creates sibling lock files named like `<resource>.lock`.

## `diskcache`

Install:

```bash
pip install coryl[diskcache]
```

What it enables:

- `app.caches.diskcache(...)`
- `app.caches.add(..., backend="diskcache")`
- `DiskCacheResource`

Notes:

- This backend is local-filesystem-only.
- Values are stored in `diskcache`, not in Coryl's inspectable file-backed cache
  layout.

## `fsspec`

Install:

```bash
pip install coryl[fsspec]
```

What it enables:

- `Coryl.with_fs(...)`
- `Coryl(..., filesystem="fsspec", protocol=...)`

Typical use:

```python
from coryl import Coryl

app = Coryl.with_fs("memory://demo", protocol="memory")
```

Notes:

- The implementation is intentionally conservative.
- `open()`, `lock()`, `watch()`, layered config, and the diskcache backend do not work
  on fsspec managers.

## `platform`

Install:

```bash
pip install coryl[platform]
```

What it enables:

- `Coryl.for_app(...)`

What `for_app(...)` does:

- Uses `platformdirs` to choose config, cache, data, and log roots
- Keeps assets under the data root

## `pydantic`

Install:

```bash
pip install coryl[pydantic]
```

What it enables:

- `ConfigResource.load_typed(...)`
- `ConfigResource.save_typed(...)`
- Typed schema registration via `app.configs.add(..., schema=MyModel)`

Notes:

- Coryl expects a Pydantic v2-style interface with `model_validate()` and
  `model_dump(mode="json")`.
- The extra installs both `pydantic` and `pydantic-settings`, but Coryl's current
  public API uses the Pydantic validation and dump interface directly.

## `watch`

Install:

```bash
pip install coryl[watch]
```

What it enables:

- `Resource.watch(...)`
- `ConfigResource.watch_reload(...)`
- `ConfigResource.on_change(...)`

Notes:

- Watching is local-filesystem-only.
- The helpers are blocking iterators and callbacks, not a background service.

## `cli`

Install:

```bash
pip install coryl[cli]
```

Current behavior:

- The `cli` extra is declared, but it adds no additional dependencies.
- The `coryl` console script is already installed by the core package.

Practical takeaway:

`pip install coryl` is enough to run the CLI unless your manifest or resources need
other extras such as `diskcache` or `yaml`.

## `all`

Install:

```bash
pip install coryl[all]
```

What it includes:

- `platformdirs>=4`
- `pydantic>=2`
- `pydantic-settings>=2`
- `diskcache>=5`
- `watchfiles>=0.21`
- `fsspec>=2024`
- `filelock>=3`
- `PyYAML>=6.0`

Practical use:

Use `all` when you want the full optional feature set without choosing extras one by
one.
