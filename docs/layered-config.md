# Layered Config

`LayeredConfigResource` keeps layered config explicit and small.

It is meant for applications that want a few ordered config files, optional secrets, environment overrides, and runtime overrides without adding a larger config framework.

Layered config currently requires the default local filesystem and is not available on fsspec-backed managers.

## Basic Usage

```python
from coryl import Coryl

app = Coryl(root=".")

settings = app.configs.layered(
    "settings",
    files=[
        "config/defaults.toml",
        "config/local.toml",
        "config/production.toml",
    ],
    env_prefix="MYAPP",
    secrets="config/.secrets.toml",
)

print(settings.as_dict())
print(settings.get("database.host"))
```

The compatibility form still works when you only need one config file plus a mounted secrets directory:

```python
settings = app.configs.layered(
    "settings",
    "config/settings.toml",
    secrets_dir="/run/secrets",
)
```

## Merge Order

Layers are applied in this order:

1. the files listed in `files=[...]`
2. `secrets=...`
3. `secrets_dir=...`
4. environment variables from `env_prefix=...`
5. runtime overrides from `override(...)` and `apply_overrides(...)`

Later layers win.

## Merge Rules

- dictionaries are deep-merged
- lists are replaced
- scalar values are replaced

## Environment Variables

Use `env_prefix="MYAPP"` to read values like:

```bash
MYAPP_DATABASE__HOST=localhost
MYAPP_DATABASE__PORT=5432
MYAPP_DEBUG=true
```

Double underscores create nesting, so `MYAPP_DATABASE__HOST` becomes `database.host`.

Parsing is conservative:

- `true` and `false` become booleans
- `null` and `none` become `None`
- integers and floats are parsed when unambiguous
- JSON arrays and objects are parsed
- everything else stays a string

## Runtime Overrides

```python
settings.override({"database.host": "localhost", "debug": True})
settings.apply_overrides(["database.port=5432"])
```

Useful helpers:

- `settings.as_dict()`
- `settings.get("key.path", default=None)`
- `settings.require("key.path")`
- `settings.reload()`

## Writes

Layered configs still behave like config resources for writes.

The writable path is:

- the single path passed in the compatibility form
- the last file in `files=[...]` for the multi-file form

`load()` and `as_dict()` return the merged view. `save(...)`, `save_typed(...)`, and `update(...)` write to the writable file layer.

## Optional Helpers

- `pip install coryl[pydantic]` adds typed config helpers.
- `pip install coryl[watch]` adds blocking watch and reload helpers.
- `pip install coryl[yaml]` adds YAML layered config files.
