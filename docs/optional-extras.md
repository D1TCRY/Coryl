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

Optional dependencies are loaded lazily. Coryl imports them only when you use the
related feature, then raises `CorylOptionalDependencyError` with the matching
`pip install coryl[...]` hint.

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
- If missing, entering `Resource.lock(...)` raises `CorylOptionalDependencyError` with
  `pip install coryl[lock]`.

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
- If missing, registering or using the backend raises `CorylOptionalDependencyError`
  with `pip install coryl[diskcache]`.

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
- If missing, `Coryl.with_fs(...)` and `Coryl(..., filesystem="fsspec", ...)` raise
  `CorylOptionalDependencyError` with `pip install coryl[fsspec]`.

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
- If missing, `Coryl.for_app(...)` raises `CorylOptionalDependencyError` with
  `pip install coryl[platform]`.

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
- If missing, `load_typed()` and `save_typed()` raise `CorylOptionalDependencyError`
  with `pip install coryl[pydantic]`.
- If Pydantic v1 is installed, Coryl still raises `CorylOptionalDependencyError`
  because typed helpers require the v2 API.

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
- If missing, `watch()`, `watch_reload()`, and `on_change()` raise
  `CorylOptionalDependencyError` with `pip install coryl[watch]`.

## `yaml`

Install:

```bash
pip install coryl[yaml]
```

What it enables:

- `read_yaml()` and `write_yaml()`
- YAML manifest loading
- YAML layered-config files

Notes:

- JSON and TOML stay in the core install; YAML is the only structured format that
  needs an extra.
- If missing, YAML reads, writes, and manifest loading raise
  `CorylOptionalDependencyError` with `pip install coryl[yaml]`.

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

If a CLI command touches a resource that depends on a missing extra, the same lazy
runtime error is raised with the matching install hint.

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
