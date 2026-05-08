# Coryl Examples

Every example creates its own temporary project root, uses only local files, and prints a small JSON payload so it is easy to inspect manually and easy to validate with `pytest`.

Run one example:

```bash
python examples/simple_local_app.py
```

Run the whole example suite:

```bash
pytest -q tests/test_examples.py
```

Included scripts:

- `simple_local_app.py`: `Coryl(root=...)` with TOML config, JSON config, cache, and asset lookup
- `cli_tool_config.py`: create a default config, update it, and print a value
- `api_cache.py`: fake API caching with `remember_json(..., ttl=...)`
- `desktop_app_assets.py`: filesystem assets with `require()`, `files()`, and `glob()`
- `manifest_startup.py`: write `app.toml`, load it, use configs/caches/assets, and inspect `audit_paths()`
- `package_assets.py`: package assets through `importlib.resources`, including `read_text()`, `read_bytes()`, and `copy_to()`
- `typed_config.py`: typed config loading with Pydantic when available
- `layered_config.py`: defaults, local overrides, environment overrides, and runtime overrides
- `cache_diskcache.py`: optional `diskcache` cache backend
- `fsspec_memory.py`: optional `fsspec` memory filesystem backend
- `diagnostics_cli.py`: run `coryl resources list`, `coryl resources check`, and `coryl config show`

Optional extras:

- `pip install coryl[pydantic]` for `typed_config.py`
- `pip install coryl[diskcache]` for `cache_diskcache.py`
- `pip install coryl[fsspec]` for `fsspec_memory.py`
