# Layered config

Coryl includes a lightweight layered configuration helper through `LayeredConfigResource`.

This is intentionally smaller than Dynaconf or Hydra. Coryl does not try to clone their full feature sets in this step. There is:

- no plugin system
- no implicit environment switching
- no settings discovery
- no dynamic resolvers
- no schema engine beyond the optional Pydantic helpers already documented elsewhere

The goal is a predictable merge pipeline that stays easy to reason about.

## Basic usage

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
    required=False,
)

print(settings.as_dict())
print(settings.get("database.host"))
print(settings.require("database.port"))
```

The older compatibility form still works when you only need one file plus a mounted secret directory:

```python
settings = app.configs.layered(
    "settings",
    "config/settings.yaml",
    secrets_dir="/run/secrets",
)
```

## Merge order

Layers are applied in a fixed, explicit order:

1. defaults
2. later files in `files=[...]`
3. `secrets=...`
4. environment variables with `env_prefix=...`
5. runtime overrides from `override(...)` and `apply_overrides(...)`

Later layers always win.

## Merge rules

Dictionary values are deep-merged recursively.

Lists are replaced, not concatenated.

Scalars are replaced.

Example:

```toml
# defaults.toml
features = ["a", "b"]

[database]
host = "localhost"

[database.options]
pool = 5
ssl = true
```

```toml
# local.toml
features = ["c"]

[database.options]
ssl = false
timeout = 30
```

Result:

```python
{
    "features": ["c"],
    "database": {
        "host": "localhost",
        "options": {
            "pool": 5,
            "ssl": False,
            "timeout": 30,
        },
    },
}
```

## Environment variables

Use `env_prefix="MYAPP"` to read variables such as:

```bash
MYAPP_DATABASE__HOST=localhost
MYAPP_DATABASE__PORT=5432
MYAPP_DEBUG=true
```

Double underscores create nesting, so `MYAPP_DATABASE__HOST` becomes `database.host`.

Parsing is conservative:

- `true` and `false` become booleans
- `null` and `none` become `None`
- integers are parsed as integers
- floats are parsed as floats
- JSON arrays and objects such as `[1, 2]` or `{"region": "eu"}` are parsed
- all other values stay as strings

Coryl does not try to evaluate arbitrary Python expressions or invent custom casting rules.

## Runtime overrides

Runtime overrides are applied last and stay attached to the resource until you replace them with new overrides or discard the resource.

```python
settings.override({"database.host": "localhost", "debug": True})
settings.apply_overrides(["database.port=5432", "features=[\"a\", \"b\"]"])
```

Supported helpers:

- `settings.get("database.host", default=None)`
- `settings.require("database.host")`
- `settings.as_dict()`
- `settings.reload()`
- `settings.override({...})`
- `settings.apply_overrides([...])`

## Required files

Set `required=True` when every declared layer must exist.

When `required=False`, missing files are skipped.

When `required=True`, missing files raise `FileNotFoundError` with the missing path in the message.

## Save behavior

`LayeredConfigResource` still behaves like a config resource for writes.

The resource `path` points at the top writable file layer, which is:

- the single file you passed in the compatibility form
- the last path in `files=[...]` for the multi-file form

That means `save(...)`, `save_typed(...)`, and `update(...)` write to the top writable file layer, while `load()` and `as_dict()` read the fully merged view.
