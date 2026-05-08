# Release Docs Report

Date: 2026-05-08

Target package version: `0.0.1`

## Docs Files Updated

- `README.md`
  Clarified beta maturity, made first-run expectations explicit, switched install commands to `python -m pip`, and converted release-facing links to absolute GitHub URLs so the package long description keeps useful navigation on PyPI.
- `CHANGELOG.md`
  Consolidated and expanded the `0.0.1` entry with summary, breaking changes, migration notes, optional extras, and known limitations.
- `CONTRIBUTING.md`
  Added reproducible setup, test, packaging, style, docs, and extension guidance.
- `AGENTS.md`
  Added repository rules for automated contributors, including the explicit optional-dependency and testing policies.
- `examples/README.md`
  Reworked into a release-facing example table with dependencies, commands, and expected output summaries.
- `docs/optional-extras.md`
  Normalized install commands to `python -m pip`.
- `pyproject.toml`
  Aligned the package version with the current release docs at `0.0.1`.
- `MANIFEST.in`
  Added `CONTRIBUTING.md` and `AGENTS.md` to the sdist.
- `tests/test_documentation_consistency.py`
  Added guardrails for the new contributor/agent docs and the examples table.
- `tests/test_release_readiness.py`
  Added checks for the aligned version and expanded release-doc packaging expectations.

## Final Docs Release Check

| Check | Status | Notes |
| --- | --- | --- |
| README first-run experience is clear | Pass | README now states beta maturity and explains that Coryl creates files relative to the configured root. |
| Install commands are correct | Pass | Release-facing install commands now consistently use `python -m pip`. |
| Optional extras are correct | Pass | README, `docs/optional-extras.md`, tests, and `tox.ini` agree on `platform`, `pydantic`, `diskcache`, `watch`, `fsspec`, `lock`, `cli`, `yaml`, and `all`. |
| Examples are runnable | Pass | Verified through `python -m pytest -q tests/test_examples.py` and the full test suite. |
| Docs do not promise unsupported behavior | Pass | Docs continue to describe `fsspec`, locks, watch helpers, and package assets conservatively. |
| Limitations are explicit | Pass | README, changelog, and `docs/limitations.md` all call out the current boundaries. |

## Examples Verified

Verified commands:

- `python -m pytest -q tests/test_examples.py`
  Passed as part of the release-facing subset.
- `python -m tox -q`
  Passed for `core`, `all`, `pydantic`, `diskcache`, `fsspec`, `platform`, `watch`, and `lock`.
- `python -m pytest -q`
  Passed with `328 passed, 3 skipped, 14 subtests passed`.

Behavior note:

- Optional examples still fail soft by design. When the matching extra is missing, they print a small JSON skip payload instead of crashing. That behavior is documented and tested.

## Packaging Docs Status

Build and render checks:

- `python -m build --sdist --wheel`
  Passed and produced:
  - `dist/coryl-0.0.1.tar.gz`
  - `dist/coryl-0.0.1-py3-none-any.whl`
- `python -m twine check dist/*`
  Passed for both artifacts, so the configured `README.md` renders as a valid long description.

Artifact inspection summary:

- sdist:
  - includes `AGENTS.md`, `CONTRIBUTING.md`, `CHANGELOG.md`, `README.md`
  - includes `docs/`, `examples/`, `tests/`, and `src/coryl/py.typed`
  - excludes `.pyc` files and `__pycache__`
- wheel:
  - includes only runtime package files plus `.dist-info` metadata and the license file
  - excludes `docs/`, `examples/`, `tests/`, `AGENTS.md`, and `CONTRIBUTING.md`

Metadata alignment:

- `pyproject.toml` and `CHANGELOG.md` now agree on `0.0.1`.

## Remaining Documentation Risks

- Coryl is still a beta library. The docs now say that plainly, but public readers may still expect broader cross-filesystem behavior than the project currently aims to provide.
- README links now point to the GitHub `main` branch so they work from the package long description. If the default branch or repository path changes, those links must be updated.
- Optional examples are documented honestly, but their full positive-path behavior still depends on installing the matching extra or using the existing `tox` environments.
