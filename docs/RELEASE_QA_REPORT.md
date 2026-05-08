# Coryl Release QA Report

Date: 2026-05-08

Release verdict: Ready to tag/publish

Release scope checked:
- Correctness
- Packaging
- README/docs/examples
- Public API coverage
- Import/performance
- CLI behavior

## Summary

The release gate pass is green after two QA-only changes:

1. `examples/diskcache_optional.py` now closes the underlying `diskcache` handle before Windows temp-dir cleanup.
2. `tests/test_release_readiness.py` now explicitly covers the remaining exported runtime names and public conflict/missing-resource error paths.

No new features were added.

## Command Results

| Command | Result |
| --- | --- |
| `python -m pytest -q` | `324 passed, 3 skipped, 14 subtests passed in 14.59s` |
| `python -m pytest -q -rs` | Same pass count; skip reasons captured below |
| `python -m tox -q` | `core`, `all`, `pydantic`, `diskcache`, `fsspec`, `platform`, `watch`, and `lock` all passed |
| `python -m pytest -q tests/test_release_readiness.py tests/test_examples.py -k "readme_python_examples_run or test_examples_run or test_typed_config_example_runs_with_fake_pydantic or test_examples_execute"` | `16 passed, 7 deselected in 5.40s` |
| `python -m pytest -q tests/test_cli.py tests/test_cli_integration.py` | `11 passed in 3.07s` |
| `python scripts/benchmark_basic.py --import-runs 10 --iterations 100` | Completed successfully; timings listed below |
| `python -m build --sdist --wheel` | Built `dist/coryl-0.0.1.tar.gz` and `dist/coryl-0.0.1-py3-none-any.whl` successfully |
| Coverage command | Skipped: `coverage` is not installed and `pytest --help` does not expose `--cov` |
| Type checker | Skipped: no configured `mypy`/`pyright` setup found in repo config |
| Linter/formatter | Skipped: no configured `ruff`/`black`/`flake8`/`pylint` setup found in repo config |

## Optional Extras Tested

Verified through `tox`:

- `all`
- `pydantic`
- `diskcache`
- `fsspec`
- `platform`
- `watch`
- `lock`

Core install also passed independently with the default `pytest` run.

## Coverage And Public API Confidence

Coverage report generation was not available in this environment because neither `coverage` nor `pytest-cov` is installed.

Public API confidence: High

Reasoning:

- The full default suite passed.
- The full extras matrix passed.
- README Python blocks execute successfully.
- Example scripts execute successfully, including optional-example paths under the appropriate extras.
- A post-pass scan of exported runtime names found no remaining unmentioned exports in tests/examples.

Previously unmentioned exported runtime names that are now explicitly covered:

- `AssetNamespace`
- `CacheNamespace`
- `ConfigNamespace`
- `DataNamespace`
- `LogNamespace`
- `CorylResourceNotFoundError`
- `ResourceConflictError`
- `ResourceRole`

## README Code Blocks

README verification status: Passed

- All Python code blocks in `README.md` were executed by `tests/test_release_readiness.py`.
- The package-assets README snippet also ran successfully.
- No README snippet changes were required in this pass.

## Import And Performance

Default import behavior: Passed

- `import coryl` remains lazy/lightweight.
- The release-readiness tests confirmed that a plain import does not eagerly import optional heavy dependencies such as `pydantic`, `diskcache`, `watchfiles`, `fsspec`, `platformdirs`, `yaml`, or `filelock`.
- The default public API flow also stayed free of optional dependency imports.

`scripts/benchmark_basic.py` results:

| Benchmark | Average ms | Min ms | Runs |
| --- | ---: | ---: | ---: |
| `import coryl` | 15.709 | 12.908 | 10 |
| `Coryl(root='.')` | 0.178 | 0.115 | 100 |
| register 10 resources | 27.647 | 21.413 | 100 |
| JSON save/load | 5.351 | 4.413 | 100 |
| `cache.remember_json` | 26.024 | 21.354 | 100 |

## Build And Package Inspection

Artifacts built:

- `dist/coryl-0.0.1.tar.gz`
- `dist/coryl-0.0.1-py3-none-any.whl`

Packaging checks:

- `py.typed` is included in both the wheel and sdist.
- Wheel contents are intentionally minimal: package modules plus metadata/license only.
- Wheel does not include `docs/`, `examples/`, or `tests/`.
- sdist includes package source, metadata, license, README, and tests.
- sdist does not include `docs/` or `examples/`.

Examples/docs inclusion policy note:

- There is no explicit MANIFEST policy for `docs/` or `examples/`.
- Current behavior is implicit setuptools default behavior: exclude docs/examples from both artifacts, include tests in sdist.
- This is acceptable for release, but if shipping offline examples/docs in the sdist matters, that policy should be made explicit in a future packaging pass.

## Skipped Tests And Why

Default environment skips:

- `tests/test_cache_diskcache.py`: skipped because `diskcache` is not installed in the base environment.
- `tests/test_config_watch.py` (2 tests): skipped because `watchfiles` is not installed in the base environment.

Extras-matrix skips:

- `tests/test_fsspec_filesystem.py` (2 tests in the `fsspec` tox env): skipped because `yaml` is not installed there; those tests require the separate `yaml` extra rather than the `fsspec` extra.

## Known Limitations

- Coverage reporting is not configured/available in this environment.
- No type-checker configuration is present, so static typing was validated only indirectly through the test suite and typed-package metadata checks.
- No linter/formatter configuration is present, so style/lint validation was not part of the release contract.
- `python -m build` writes progress to stderr under PowerShell; the build still completed successfully and produced valid artifacts.
- `docs/` and `examples/` are not included in the current artifacts.

## Recommended Version Bump

Recommended bump: Patch

Suggested next version: `0.0.2`

Why:

- The only code change was a correctness fix in an example used by the release matrix.
- The remaining change was test-only public API coverage.
- No public API shape or default behavior changed.

## Release Blockers

None at the end of this pass.
