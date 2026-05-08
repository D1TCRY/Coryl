# Changelog

All notable changes to Coryl will be documented in this file.

## 0.0.2 - 2026-05-08

### Changed

- Added explicit release-quality tooling config for coverage, mypy, and Ruff.
- Added an explicit `MANIFEST.in` so sdists include docs, examples, tests, and release metadata while wheels stay runtime-minimal.
- Updated the `tox` `fsspec` environment to install the separate `yaml` extra so YAML-backed fsspec tests run there.
- Removed tracked bytecode/build artifacts and added ignore rules for generated QA/build output.
- No Coryl runtime features or public APIs changed in this release.

## 0.0.1 - 2026-05-08

### Added

- Core safety checks for managed roots, child paths, and manifest-driven resources.
- Atomic writes for the default local filesystem.
- Optional inter-process locks through `coryl[lock]`.
- `Coryl.for_app(...)` with optional OS app directories through `coryl[platform]`.
- Package asset access through `importlib.resources`.
- Optional typed config helpers through `coryl[pydantic]`.
- Layered config helpers for ordered files, secrets, environment values, and runtime overrides.
- Cache TTL helpers for the default file-oriented cache.
- Optional `diskcache` backend through `coryl[diskcache]`.
- Optional watch and reload helpers through `coryl[watch]`.
- Optional advanced filesystem support through `coryl[fsspec]`.
- Diagnostics CLI commands through `coryl[cli]`.

### Changed

- The default `Coryl(root=".")` flow stays local, lightweight, and dependency-minimal.
- Optional integrations are imported only when the matching feature is used.
