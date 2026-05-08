# Changelog

All notable changes to Coryl are documented in this file.

## 0.0.2 - 2026-05-08

### Summary

- Packaging metadata patch release for Coryl 0.0.2.
- Published the GitHub repository as the package `Home-Page`.

### Changed

- Updated `pyproject.toml` project metadata so `Home-Page` points to `https://github.com/D1TCRY/Coryl`.

### Breaking changes

- None.

### Migration notes

- If you built local artifacts for `0.0.1`, rebuild or reinstall so package metadata reports `0.0.2` and the GitHub repository `Home-Page`.

## 0.0.1 - 2026-05-08

### Summary

- First tagged public API baseline for Coryl's local resource manager and optional integrations.
- Release-prep pass focused on packaging, documentation clarity, and reproducible QA.

### Added

- Core safety checks for managed roots, child paths, and manifest-driven resources.
- Local resource namespaces for configs, caches, assets, data, and logs under `Coryl(root=".")`.
- Atomic writes for the default local filesystem.
- Package asset access through `importlib.resources`.
- Optional YAML reads, writes, manifest loading, and layered-config files through `coryl[yaml]`.
- Optional inter-process locks through `coryl[lock]`.
- `Coryl.for_app(...)` with optional OS app directories through `coryl[platform]`.
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
- Added explicit release-quality tooling config for coverage, mypy, and Ruff.
- Added an explicit `MANIFEST.in` so sdists include docs, examples, tests, and release metadata while wheels stay runtime-minimal.
- Updated the `tox` `fsspec` environment to install the separate `yaml` extra so YAML-backed fsspec tests run there.
- Tightened the public docs around first-run setup, optional extras, examples, and known limitations.
- Removed tracked bytecode/build artifacts and added ignore rules for generated QA/build output.

### Breaking changes

- None in the initial public release.

### Migration notes

- No migration path is required from an earlier tagged package release.
- Legacy manifest files still load, but new work should use manifest schema version `2`.
- If you built local artifacts before this alignment pass, rebuild or reinstall so package metadata and the changelog both report `0.0.1`.

### Optional extras

- The initial public release ships with `platform`, `pydantic`, `diskcache`, `watch`, `fsspec`, `lock`, `cli`, `yaml`, and `all`.
- The `cli` extra still exists for compatibility and discoverability, but the console script already ships in the core install.
- JSON and TOML stay in the core install; YAML is the only structured format gated behind an extra.
- Optional dependencies remain lazy: Coryl imports them only when you use the related feature.

### Known limitations

- Coryl is a local-first resource layer, not a distributed cache, remote lock service, or larger application framework.
- The default local-filesystem manager remains the simplest and best-covered workflow.
- `lock`, `watch`, and layered-config helpers are local-filesystem features.
- `fsspec` support is intentionally conservative and does not provide `open()`, locking, watching, layered config, the `diskcache` backend, or local atomic replace semantics.
- Package assets are read-only and do not promise stable on-disk paths.
- `fsspec`, watch helpers, and package assets have explicit behavior boundaries documented in `docs/limitations.md`.
