# Limitations

This page documents the current behavior implemented in `src/coryl`.

## fsspec Limitations

fsspec support is opt-in through `Coryl.with_fs(...)` or
`Coryl(..., filesystem="fsspec")`.

What works:

- resource registration
- text and bytes I/O
- JSON and TOML structured I/O
- YAML structured I/O when `coryl[yaml]` is installed
- directory globbing
- the built-in file-backed cache helpers

What does not work on fsspec-backed managers:

- `Resource.open()`
- `Resource.lock()`
- `Resource.watch()`
- `ConfigResource.watch_reload()`
- `ConfigResource.on_change()`
- `register_layered_config(...)`
- `LayeredConfigResource`
- `backend="diskcache"`

Write behavior difference:

- Local resources use atomic replace writes by default.
- fsspec resources fall back to regular writes even when `atomic=True`.

Path behavior difference:

- Local managers expose local `Path` objects.
- fsspec managers expose logical `PurePosixPath` paths rooted under the configured
  backend URI.

## Local-Only Locks

`Resource.lock()` is designed for the default local filesystem.

Current behavior:

- requires `coryl[lock]`
- uses `filelock.FileLock`
- creates a sibling lock file named `<resource>.lock`
- raises `CorylLockTimeoutError` when acquisition times out

What this is not:

- not a distributed lock
- not a remote filesystem lock
- not a cross-backend locking abstraction

## Watch Behavior

Watch helpers are intentionally small and blocking.

Current behavior:

- requires `coryl[watch]`
- uses `watchfiles.watch(...)`
- only works on the default local filesystem
- `Resource.watch(...)` yields raw change sets
- `ConfigResource.watch_reload(...)` yields reloaded config documents
- `ConfigResource.on_change(...)` runs a callback for each reloaded document

Layered config watch scope:

- layer files are watched
- `secrets=...` files are watched
- `secrets_dir=...` directories are watched

Changes that are not watched directly:

- environment variable changes from `env_prefix=...`
- runtime overrides applied with `override(...)` or `apply_overrides(...)`

Operational note:

These helpers do not start a background thread or a persistent daemon. They block while
waiting for filesystem events.

## Package Asset Path Limitations

Package-backed assets intentionally avoid promising stable filesystem paths.

Current behavior:

- `PackageAssetGroup.path` always raises `CorylPathError`
- `PackageAssetResource.path` always raises `CorylPathError`
- `display_path` uses `package://...` URIs for readable diagnostics
- `PackageAssetResource.as_file()` materializes a temporary local file path when
  needed
- `PackageAssetGroup.copy_to(...)` copies a full asset tree to a local directory

Practical implication:

Use `read_text()`, `read_bytes()`, `file(...).as_file()`, or `copy_to(...)` instead of
assuming a package asset has a permanent on-disk path.

## What Coryl Is Not

### Not Redis

Coryl caches are local application resources.

What that means in practice:

- `CacheResource` is file-backed and inspectable on disk
- `DiskCacheResource` is still local to one machine and one filesystem
- there is no network server, remote protocol, or distributed cache coordination

Use Coryl when you want application-owned local cache storage, not a shared cache
service.

### Not Full Hydra

`LayeredConfigResource` gives you explicit file layering, environment overrides,
secrets, and runtime overrides.

What it does not try to provide:

- a config composition language
- config groups
- launchers or sweepers
- experiment orchestration

Use Coryl layered config when you want a small, explicit layering model without a
larger framework.

### Not Full Dynaconf

Coryl supports structured config files, optional typed validation, simple environment
overrides, and a small layered-config model.

What it does not try to provide:

- a large multi-backend settings ecosystem
- automatic loaders for many external systems
- a global mutable settings object with framework-wide conventions

Use Coryl when you want safe paths and a small resource layer first, not a full
settings platform.
