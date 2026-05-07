# Coryl Implementation Roadmap

This document captures the current implementation state of Coryl and proposes a phased roadmap for future work.

## Audit Snapshot

### Package Structure

- `src/coryl/__init__.py`: public API surface
- `src/coryl/exceptions.py`: package-specific exceptions
- `src/coryl/serialization.py`: JSON, TOML, and YAML format helpers
- `src/coryl/resources.py`: resource models and specialized resource classes
- `src/coryl/manager.py`: `ResourceManager`, `Coryl`, and typed namespaces
- `tests/test_coryl.py`: current unit coverage
- `pyproject.toml`: packaging metadata and lightweight runtime dependencies
- `README.md`: user-facing documentation

### Current Implementations

- `Coryl / ResourceManager`
  Manages a root directory, registers resources, exposes compatibility helpers, typed namespaces (`configs`, `caches`, `assets`), and manifest loading.
- `Resource`
  Generic file or directory abstraction with safe child-path handling plus text, bytes, and structured data helpers.
- `ConfigResource`
  Structured file resource with `load()`, `save()`, and shallow `update()` support.
- `CacheResource`
  Managed directory for cached files with `remember()`, `load()`, `delete()`, and `clear()`.
- `AssetGroup`
  Managed directory for asset lookup, traversal, and existence checks.
- `ResourceSpec`
  Immutable declaration object with typed constructors for generic resources, config files, cache directories, and asset directories.
- `Manifest loading`
  Modern-schema only. Manifests must provide a top-level `resources` mapping and can be written in JSON, TOML, or YAML.
- `Path resolution / safety checks`
  Paths are resolved relative to `root`, rejected if they escape the root, and directory child resources are constrained to stay inside the parent directory.
- `JSON / TOML / YAML support`
  Implemented in `serialization.py`, with `tomllib` or `tomli` for TOML loading and `PyYAML` for YAML.

### Current Design Notes

- The public API is already small and practical.
- The package remains lightweight; current mandatory dependencies are limited to `PyYAML` and a Python-version-specific `tomli` fallback.
- FileManager-style helpers still exist and should be preserved where feasible.
- Manifest compatibility has intentionally been simplified to the modern schema only.

## Roadmap Principles

- Preserve the existing public API wherever possible.
- Keep the library lightweight, fast, and easy to reason about.
- Prefer optional extras for integrations or non-core capabilities.
- Maintain Python 3.10+ support and type hints across public APIs.

## Phase 1: Core Safety and Reliability

- Tighten manifest validation and improve error messages around malformed resource definitions.
- Audit edge cases in the custom TOML writer and document supported value shapes clearly.
- Add focused tests for invalid formats, invalid roles, duplicate registrations, and manifest reload behavior.
- Review broad exception handling in `content()` and structured loaders to avoid masking important errors unintentionally.

## Phase 2: OS-Specific App Directories

- Add helpers to derive standard application directories for config, cache, data, and state across Windows, macOS, and Linux.
- Keep this layer opt-in and dependency-free.
- Ensure generated directories compose cleanly with the existing `ResourceManager` API.

## Phase 3: Package Assets

- Add first-class support for assets shipped inside installed Python packages.
- Prefer standard library mechanisms such as `importlib.resources`.
- Keep the current filesystem API intact while adding a small, clear access layer for packaged resources.

## Phase 4: Typed Config

- Add optional typed config loading built around standard dataclasses or user-provided converter functions.
- Do not make Pydantic or other heavy frameworks mandatory.
- Keep the base `ConfigResource.load()` behavior unchanged for plain dictionary workflows.

## Phase 5: Layered Config

- Support layered configuration from multiple sources such as defaults, local overrides, environment-specific files, and user overrides.
- Define explicit merge semantics and keep them predictable.
- Keep the initial implementation file-based before considering environment-variable expansion.

## Phase 6: Cache Improvements

- Add cache metadata helpers such as timestamps, age checks, and stale-entry cleanup.
- Consider atomic writes for cache files and optional temp-file swap logic.
- Preserve the simplicity of the current `remember()` and `load()` workflow.

## Phase 7: Watch / Reload

- Introduce optional file watching for config reload scenarios.
- Keep this capability out of the core dependency set by using optional extras.
- Design the API so polling-based fallback remains possible without platform-specific complexity in the core package.

## Phase 8: Optional Remote Filesystem Support

- Explore optional adapters for cloud or remote filesystems.
- Keep the core local-filesystem model as the default and primary path.
- Put integrations behind extras and a narrow adapter boundary to avoid bloating the main package.

## Phase 9: CLI Diagnostics

- Add a small CLI for validation and diagnostics only after the core API is stable.
- Useful first commands:
  - validate a manifest
  - print resolved resource paths
  - check for missing files or directories
  - display structured config parse results
- Keep the CLI lightweight and based on the standard library where practical.

## Suggested Execution Order

1. Finish Phase 1 before adding new capability layers.
2. Implement OS-specific directories and package-asset support next because they naturally extend the current model.
3. Add typed and layered config once the config surface is stable.
4. Add cache, watch/reload, remote adapters, and CLI diagnostics afterward as mostly additive features.
