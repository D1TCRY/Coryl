# Documentation Matrix

This matrix treats `src/coryl` and the current passing tests as the source of truth.

Status meanings:

- `Aligned`: README, docs, examples, and tests agree with implemented behavior.
- `Docs-only`: the README snippet is intentionally conceptual, with runtime coverage in
  tests and nearby examples.

## Feature Matrix

| Feature | README section | docs page | example file | test file | status |
| --- | --- | --- | --- | --- | --- |
| Core install and lazy optional imports | `Installation` | `docs/optional-extras.md` | `n/a` | `tests/test_packaging_optional_dependencies.py`, `tests/test_dependency_matrix.py` | Aligned |
| Local manager, namespaces, safe roots | `Quick Start`, `Core Concepts`, `Safety Model` | `docs/api-reference.md` | `examples/simple_local_app.py` | `tests/test_coryl.py`, `tests/test_core_manager_filesystem.py` | Aligned |
| Structured file I/O, including YAML | `Files and Structured Data`, `Manifests` | `docs/api-reference.md`, `docs/optional-extras.md` | `examples/simple_local_app.py` | `tests/test_structured_formats_filesystem.py`, `tests/test_dependency_matrix.py` | Aligned |
| Basic config helpers | `Configs` / `Basic config` | `docs/api-reference.md` | `examples/cli_tool_config.py` | `tests/test_config_basic.py` | Aligned |
| Typed config helpers | `Configs` / `Typed config` | `docs/api-reference.md`, `docs/optional-extras.md` | `examples/typed_config.py` | `tests/test_config_typed.py`, `tests/test_packaging_optional_dependencies.py` | Aligned |
| Layered config, env overrides, and secrets | `Configs` / `Layered config`, `Env overrides`, `Secrets` | `docs/layered-config.md`, `docs/limitations.md` | `examples/layered_config.py` | `tests/test_config_layered.py` | Aligned |
| Config migrations | `Configs` / `Migrations` | `docs/api-reference.md` | `n/a` | `tests/test_config_migrations.py` | Aligned |
| Watch helpers | `Configs` / ``watch_reload()`` | `docs/optional-extras.md`, `docs/limitations.md`, `docs/api-reference.md` | `n/a` | `tests/test_config_watch.py`, `tests/test_packaging_optional_dependencies.py` | Aligned |
| Built-in file-backed cache | `Caches` / `Built-in file cache`, `TTL and remember helpers` | `docs/api-reference.md` | `examples/api_cache.py` | `tests/test_cache_builtin.py` | Aligned |
| Optional `diskcache` backend | `Caches` / `DiskCache backend` | `docs/optional-extras.md`, `docs/limitations.md`, `docs/api-reference.md` | `examples/cache_diskcache.py` | `tests/test_cache_diskcache.py`, `tests/test_cache_diskcache_optional.py` | Aligned |
| Filesystem assets | `Assets` / `Filesystem assets` | `docs/api-reference.md` | `examples/desktop_app_assets.py` | `tests/test_assets_filesystem.py` | Aligned |
| Package assets and `copy_to(...)` | `Assets` / `Package assets`, ``copy_to()`` bootstrap | `docs/api-reference.md`, `docs/limitations.md` | `examples/package_assets.py` | `tests/test_assets_package.py` | Aligned |
| Installed app roots via `platformdirs` | `Installed Apps` | `docs/optional-extras.md`, `docs/api-reference.md` | `n/a` | `tests/test_packaging_optional_dependencies.py`, `tests/test_dependency_matrix.py` | Aligned |
| Manifest loading, v2 schema, and legacy compatibility | `Manifests` | `docs/api-reference.md` | `examples/manifest_startup.py` | `tests/test_manifest_compatibility.py` | Aligned |
| Diagnostics CLI | `Diagnostics CLI` | `docs/api-reference.md` | `examples/diagnostics_cli.py` | `tests/test_cli.py`, `tests/test_cli_integration.py` | Aligned |
| Optional `fsspec` managers | `Advanced Filesystems` | `docs/optional-extras.md`, `docs/limitations.md` | `examples/fsspec_memory.py` | `tests/test_fsspec_filesystem.py`, `tests/test_fsspec_optional.py` | Aligned |
| Local-only resource locking | `Installation`, `Safety Model` | `docs/optional-extras.md`, `docs/limitations.md`, `docs/api-reference.md` | `n/a` | `tests/test_coryl.py`, `tests/test_packaging_optional_dependencies.py`, `tests/test_fsspec_filesystem.py` | Aligned |
| Example catalog and fresh-checkout behavior | `Examples` | `examples/README.md` | `examples/*.py` | `tests/test_examples.py`, `tests/test_release_readiness.py` | Aligned |

Internal docs scanned but intentionally excluded from the feature rows:

- `docs/QA_CHECKLIST.md`
- `docs/RELEASE_QA_REPORT.md`
- `docs/ROADMAP_IMPLEMENTATION.md`

These files describe QA and release workflow rather than user-facing runtime behavior.

## README Code Block Coverage

| Feature | README section | docs page | example file | test file | status |
| --- | --- | --- | --- | --- | --- |
| Install core package | `Installation` | `docs/optional-extras.md` | `n/a` | `tests/test_packaging_optional_dependencies.py` | Aligned |
| Quick start local manager snippet | `Quick Start` | `docs/api-reference.md` | `examples/simple_local_app.py` | `tests/test_release_readiness.py::test_readme_python_examples_run` | Aligned |
| Generic file and structured-data snippet | `Files and Structured Data` | `docs/api-reference.md` | `n/a` | `tests/test_structured_formats_filesystem.py`, `tests/test_release_readiness.py::test_readme_python_examples_run` | Aligned |
| Basic config snippet | `Configs` / `Basic config` | `docs/api-reference.md` | `examples/cli_tool_config.py` | `tests/test_config_basic.py`, `tests/test_release_readiness.py::test_readme_python_examples_run` | Aligned |
| Typed config snippet | `Configs` / `Typed config` | `docs/optional-extras.md`, `docs/api-reference.md` | `examples/typed_config.py` | `tests/test_config_typed.py`, `tests/test_release_readiness.py::test_readme_python_examples_run` | Aligned |
| Layered config snippet | `Configs` / `Layered config` | `docs/layered-config.md` | `examples/layered_config.py` | `tests/test_config_layered.py`, `tests/test_release_readiness.py::test_readme_python_examples_run` | Aligned |
| Config migration snippet | `Configs` / `Migrations` | `docs/api-reference.md` | `n/a` | `tests/test_config_migrations.py`, `tests/test_release_readiness.py::test_readme_python_examples_run` | Aligned |
| Conceptual `watch_reload()` loop | `Configs` / ``watch_reload()`` | `docs/optional-extras.md`, `docs/limitations.md` | `n/a` | `tests/test_config_watch.py`, `tests/test_packaging_optional_dependencies.py` | Docs-only |
| Built-in cache snippet | `Caches` / `Built-in file cache` | `docs/api-reference.md` | `examples/api_cache.py` | `tests/test_cache_builtin.py`, `tests/test_release_readiness.py::test_readme_python_examples_run` | Aligned |
| `diskcache` snippet | `Caches` / `DiskCache backend` | `docs/optional-extras.md` | `examples/cache_diskcache.py` | `tests/test_cache_diskcache.py`, `tests/test_cache_diskcache_optional.py`, `tests/test_release_readiness.py::test_readme_python_examples_run` | Aligned |
| Filesystem assets snippet | `Assets` / `Filesystem assets` | `docs/api-reference.md` | `examples/desktop_app_assets.py` | `tests/test_assets_filesystem.py`, `tests/test_release_readiness.py::test_readme_python_examples_run` | Aligned |
| Conceptual package-assets snippet | `Assets` / `Package assets` | `docs/api-reference.md`, `docs/limitations.md` | `examples/package_assets.py` | `tests/test_assets_package.py` | Docs-only |
| Conceptual `copy_to(...)` snippet | `Assets` / ``copy_to()`` bootstrap | `docs/api-reference.md`, `docs/limitations.md` | `examples/package_assets.py` | `tests/test_assets_package.py` | Docs-only |
| Installed-app roots snippet | `Installed Apps` | `docs/optional-extras.md`, `docs/api-reference.md` | `n/a` | `tests/test_packaging_optional_dependencies.py`, `tests/test_dependency_matrix.py`, `tests/test_release_readiness.py::test_readme_python_examples_run` | Aligned |
| Manifest bootstrap snippet | `Manifests` | `docs/api-reference.md` | `examples/manifest_startup.py` | `tests/test_manifest_compatibility.py`, `tests/test_release_readiness.py::test_readme_python_examples_run` | Aligned |
| TOML v2 manifest block | `Manifests` / `TOML v2` | `docs/api-reference.md` | `examples/manifest_startup.py` | `tests/test_manifest_compatibility.py` | Aligned |
| JSON v2 manifest block | `Manifests` / `JSON v2` | `docs/api-reference.md` | `n/a` | `tests/test_manifest_compatibility.py` | Aligned |
| YAML v2 manifest block | `Manifests` / `YAML v2` | `docs/optional-extras.md`, `docs/api-reference.md` | `n/a` | `tests/test_manifest_compatibility.py`, `tests/test_dependency_matrix.py` | Aligned |
| Legacy manifest block | `Manifests` / `Legacy schema compatibility` | `docs/api-reference.md` | `n/a` | `tests/test_manifest_compatibility.py` | Aligned |
| `fsspec` memory snippet | `Advanced Filesystems` | `docs/optional-extras.md`, `docs/limitations.md` | `examples/fsspec_memory.py` | `tests/test_fsspec_filesystem.py`, `tests/test_fsspec_optional.py`, `tests/test_release_readiness.py::test_readme_python_examples_run` | Aligned |
