# Coryl Release QA Report

Date: 2026-05-08

Release verdict: Ready to tag/publish

Release scope checked:
- Packaging and artifact policy
- Dependency/tooling hygiene
- Test and extras matrix
- Coverage reporting
- Type-checking bootstrap
- Lint/format baseline

## Summary

This pass focused strictly on release hygiene for `0.0.1`:

- Added coverage support with `pytest-cov` and repo coverage config.
- Added a practical `mypy` baseline for the `coryl` package.
- Added `ruff` lint/format config and normalized repository formatting.
- Made the sdist artifact policy explicit with `MANIFEST.in`.
- Fixed the `tox` `fsspec` environment so YAML-backed fsspec tests no longer skip there.
- Removed tracked bytecode/old distribution artifacts and added `.gitignore` rules for generated QA/build output.
- Aligned the package version to `0.0.1` and updated `CHANGELOG.md`.

No Coryl runtime features or public APIs were added in this pass.

## Command Results

| Command | Result |
| --- | --- |
| `python -m pytest -q` | `326 passed, 3 skipped, 14 subtests passed in 11.19s` |
| `python -m tox -q` | `core`, `all`, `pydantic`, `diskcache`, `fsspec`, `platform`, `watch`, and `lock` all passed |
| `python -m pytest --cov=coryl --cov-report=term-missing` | `326 passed, 3 skipped`; total coverage `79%` |
| `python -m mypy coryl` | Passed with `Success: no issues found in 10 source files` after verifying the positional-path form against the `src/` layout via a temporary repo-root junction |
| `python -m mypy -p coryl` | Passed with `Success: no issues found in 10 source files` |
| `python -m ruff check .` | `All checks passed!` |
| `python -m ruff format --check .` | `64 files already formatted` |
| `python -m build --sdist --wheel` | Built `dist/coryl-0.0.1.tar.gz` and `dist/coryl-0.0.1-py3-none-any.whl` successfully |

## Coverage

Coverage config added:

- `source = ["coryl"]`
- `branch = true`

Coverage result:

- Total: `79%`

Lowest-covered modules after this bootstrap pass:

- `src/coryl/serialization.py`: `65%`
- `src/coryl/_io.py`: `77%`
- `src/coryl/cli.py`: `77%`
- `src/coryl/resources.py`: `78%`
- `src/coryl/_fs.py`: `79%`

Coverage is now available and reproducible instead of being an implicit skip.

## Type Checking

Type-checking support added:

- `mypy` in dependency groups
- package-targeted config in `pyproject.toml`
- `check_untyped_defs = true`
- `ignore_missing_imports = true`
- targeted bootstrap overrides for currently annotation-heavy modules:
  - `coryl.cli`
  - `coryl.manager`
  - `coryl.resources`
  - `coryl.serialization`

Notes:

- This is intentionally a practical baseline, not strict mode.
- `python -m mypy coryl` is path-based under current mypy CLI behavior, so the source-tree `src/` layout needed a temporary repo-root junction for exact-command verification.
- The underlying package-oriented invocation `python -m mypy -p coryl` also passed and checked the actual package modules.

## Lint And Format

Ruff support added:

- `ruff` in dev dependencies
- repo formatting normalized with `ruff format`
- practical lint baseline configured with `pyflakes` checks

Configured commands now pass:

- `python -m ruff check .`
- `python -m ruff format --check .`

## Packaging And Artifacts

Artifact policy is now explicit through `MANIFEST.in`.

Repo hygiene added:

- `.gitignore` now ignores build, coverage, cache, tox, egg-info, dist, and bytecode output.
- Tracked `.pyc` and old `dist/` artifacts were removed from version control.

sdist inspection confirmed:

- Includes `docs/`
- Includes `examples/`
- Includes `tests/`
- Includes `README.md`
- Includes `LICENSE`
- Includes `CHANGELOG.md`
- Includes `MANIFEST.in`
- Includes `src/coryl/py.typed`
- Does not include `.pyc` artifacts

Wheel inspection confirmed:

- Includes only runtime package modules under `coryl/`
- Includes package metadata under `.dist-info/`
- Includes the license file
- Includes `coryl/py.typed`
- Does not include `docs/`
- Does not include `examples/`
- Does not include `tests/`

Artifacts built:

- `dist/coryl-0.0.1.tar.gz`
- `dist/coryl-0.0.1-py3-none-any.whl`

## Extras Matrix

Verified through `tox`:

- `core`
- `all`
- `pydantic`
- `diskcache`
- `fsspec`
- `platform`
- `watch`
- `lock`

`fsspec` now installs the separate `yaml` extra in tox, so the YAML-backed fsspec tests execute there instead of being skipped.

## Remaining Skips

Base-environment skips from `python -m pytest -q`:

- `tests/test_cache_diskcache.py`: skipped because `diskcache` is not installed in the base environment
- `tests/test_config_watch.py` (2 tests): skipped because `watchfiles` is not installed in the base environment

These are expected optional-dependency skips and are covered by the extras matrix.

## Release Blockers

None at the end of this pass.
