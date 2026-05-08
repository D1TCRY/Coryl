# Coryl Examples

These examples are small and focused.

- `simple_local_app.py`: local project-root config, cache, and asset usage
- `cli_tool_config.py`: CLI-style config and cache usage
- `api_cache.py`: file-oriented API response caching
- `desktop_app_assets.py`: desktop-style filesystem and package assets together
- `declarative_manifest.py`: startup from `app.toml` plus `audit_paths()`
- `installed_app.py`: `Coryl.for_app(...)` with mocked `platformdirs`
- `container_config.py`: readonly config and assets with `secrets_dir`
- `diagnostics_cli.py`: manifest-driven diagnostics CLI workflow
- `package_assets.py`: read-only bundled package assets
- `typed_config.py`: typed config validation with Pydantic
- `layered_config.py`: layered config with file layers and overrides
- `diskcache_optional.py`: optional `diskcache` cache backend example
- `fsspec_memory.py`: optional `fsspec` memory filesystem example

Optional extras used by some examples:

- `pip install coryl[pydantic]`
- `pip install coryl[diskcache]`
- `pip install coryl[fsspec]`
