# Coryl Examples

Each example creates its own temporary project root, uses only local files or in-memory backends, and prints JSON to stdout so the output is easy to inspect manually and easy to validate with `pytest`.

Fresh-checkout behavior:

- Every script adds `src/` to `sys.path`, so you can run examples directly from a source checkout without installing the package first.
- Optional examples still run without their extra, but they return a small skip payload such as `{"available": false, "skipped": true, ...}` instead of failing.

Run one example:

```bash
python examples/simple_local_app.py
```

Run the full example suite:

```bash
python -m pytest -q tests/test_examples.py
```

## Example Table

| Example | Dependencies needed | Command to run | Expected output summary |
| --- | --- | --- | --- |
| `simple_local_app.py` | Core install | `python examples/simple_local_app.py` | JSON with `app_name`, `cached_user`, `debug`, `locale`, and `logo_name` from a local app root. |
| `cli_tool_config.py` | Core install | `python examples/cli_tool_config.py` | JSON showing a default config was created, updated, and read back. |
| `api_cache.py` | Core install | `python examples/api_cache.py` | JSON proving the cache factory ran once and the second read reused the cached value. |
| `desktop_app_assets.py` | Core install | `python examples/desktop_app_assets.py` | JSON listing asset files, glob matches, and the loaded template/icon values. |
| `manifest_startup.py` | Core install | `python examples/manifest_startup.py` | JSON with manifest-loaded resource names, `audit_paths()` output, cached data, and a looked-up asset. |
| `package_assets.py` | Core install | `python examples/package_assets.py` | JSON showing package asset text/bytes reads plus the copied file list from `copy_to(...)`. |
| `layered_config.py` | Core install | `python examples/layered_config.py` | JSON showing file defaults, local overrides, environment overrides, and runtime override merging. |
| `diagnostics_cli.py` | Core install | `python examples/diagnostics_cli.py` | JSON summarizing `coryl resources list`, `resources check`, and `config show` command results. |
| `typed_config.py` | `coryl[pydantic]` for full output | `python examples/typed_config.py` | With Pydantic v2: JSON with `host`, `port`, and `debug`; without it: a skip payload. |
| `cache_diskcache.py` | `coryl[diskcache]` for full output | `python examples/cache_diskcache.py` | With `diskcache`: JSON showing memoized cache reads; without it: a skip payload. |
| `fsspec_memory.py` | `coryl[fsspec]` for full output | `python examples/fsspec_memory.py` | With `fsspec`: JSON showing in-memory config/cache/assets behavior; without it: a skip payload. |

## Optional Extras

Install only the extra you need for the optional examples:

- `python -m pip install coryl[pydantic]` for `typed_config.py`
- `python -m pip install coryl[diskcache]` for `cache_diskcache.py`
- `python -m pip install coryl[fsspec]` for `fsspec_memory.py`
