# Coryl Implementation Notes

This document summarizes the current Coryl architecture and the small set of follow-up areas still worth tracking.

## Current Architecture

### Core Manager

- `Coryl(root=".")` is the default entry point.
- One manager owns one safe root plus named resources under that root.
- The public API centers on namespaces instead of many separate top-level entry points:
  - `app.configs`
  - `app.caches`
  - `app.assets`
  - `app.data`
  - `app.logs`

### Resource Types

- `Resource` handles generic files and directories.
- `ConfigResource` adds structured config helpers.
- `LayeredConfigResource` adds ordered file layers, environment overrides, secrets, and runtime overrides.
- `CacheResource` keeps the default cache model file-oriented and inspectable.
- `DiskCacheResource` is optional and only used when the `diskcache` backend is selected.
- `AssetGroup` manages filesystem-backed asset directories.
- `PackageAssetGroup` exposes bundled package assets through `importlib.resources`.

### Manifests

- Modern manifests use `version = 2` with a top-level `resources` mapping.
- Legacy `paths.files` and `paths.directories` manifests still load for compatibility.
- `load_config()` reloads the manifest content.
- `app.config` is reserved for loaded manifest data.

### Safety Rules

- managed paths are resolved relative to a root
- registrations cannot escape the managed root
- child resources created from managed directories cannot escape the parent
- read-only resources block writes, deletes, clears, and other mutations
- default local writes use atomic replacement helpers

## Optional Integrations

Optional integrations stay behind extras and are imported only when used:

- `coryl[platform]` for `Coryl.for_app(...)`
- `coryl[pydantic]` for typed config helpers
- `coryl[diskcache]` for the `diskcache` cache backend
- `coryl[watch]` for watch and reload helpers
- `coryl[fsspec]` for advanced filesystem backends
- `coryl[lock]` for inter-process locks
- `coryl[cli]` for diagnostics commands
- `coryl[yaml]` for YAML config and manifest support

## Documentation Map

- `README.md` keeps the default flow and main concepts short.
- `docs/layered-config.md` covers layered config behavior in more detail.
- `examples/` contains runnable or copyable usage patterns for the main resource types.

## Short Follow-Up List

- keep the default import path small
- add focused examples before adding new abstractions
- prefer optional extras over core dependency growth
- preserve compatibility helpers where they do not complicate the main API
