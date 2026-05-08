# Contributing to Coryl

Thanks for helping improve Coryl. The project aims to stay small, explicit, and safe by default, so contributions should favor clarity and reproducibility over cleverness.

## Development Setup

Create and activate a virtual environment:

```bash
python -m venv .venv
# PowerShell
.venv\Scripts\Activate.ps1
# bash/zsh
source .venv/bin/activate
```

Install the core package in editable mode plus the tools used in this repository:

```bash
python -m pip install --upgrade pip
python -m pip install -e .
python -m pip install pytest pytest-cov mypy "ruff>=0.11" tox build twine
```

Install all optional integrations when you want the broadest local test coverage:

```bash
python -m pip install -e ".[all]"
```

Notes:

- `pyproject.toml` declares dependency groups, but the explicit `python -m pip install ...` commands above are the most portable setup path today.
- Examples add `src/` to `sys.path`, so they also run directly from a fresh source checkout.

## Test Commands

Common commands:

```bash
python -m pytest -q
python -m pytest -q tests/test_documentation_consistency.py tests/test_release_readiness.py
python -m pytest -q tests/test_examples.py
python -m tox -q
```

Release and packaging checks:

```bash
python -m build --sdist --wheel
python -m twine check dist/*
```

Static checks:

```bash
python -m ruff check .
python -m ruff format --check .
python -m mypy -p coryl
```

## Optional Extras Test Commands

Use the matching extra when you work on optional behavior:

| Extra | Install | Focused tests |
| --- | --- | --- |
| `yaml` | `python -m pip install -e ".[yaml]"` | `python -m pytest -q tests/test_dependency_matrix.py tests/test_structured_formats_filesystem.py` |
| `pydantic` | `python -m pip install -e ".[pydantic]"` | `python -m pytest -q tests/test_config_typed.py tests/test_dependency_matrix.py` |
| `diskcache` | `python -m pip install -e ".[diskcache]"` | `python -m pytest -q tests/test_cache_diskcache.py tests/test_cache_diskcache_optional.py` |
| `fsspec` | `python -m pip install -e ".[fsspec,yaml]"` | `python -m pytest -q tests/test_fsspec_filesystem.py tests/test_fsspec_optional.py` |
| `platform` | `python -m pip install -e ".[platform]"` | `python -m pytest -q tests/test_dependency_matrix.py tests/test_packaging_optional_dependencies.py -k for_app` |
| `watch` | `python -m pip install -e ".[watch]"` | `python -m pytest -q tests/test_config_watch.py` |
| `lock` | `python -m pip install -e ".[lock]"` | `python -m pytest -q tests/test_coryl.py -k lock` |
| `all` | `python -m pip install -e ".[all]"` | `python -m pytest -q` |

`tox.ini` already captures the intended extras matrix if you want one command that exercises the packaged environments.

## Code Style

- Target the documented public floor, Python `3.10+`.
- Keep the default local `Coryl(root=".")` path simple and dependency-light.
- Preserve lazy optional imports. Optional dependencies should only be imported where the feature is used.
- Raise actionable `CorylOptionalDependencyError` messages when an optional integration is missing.
- Prefer explicit, readable helpers over framework-style magic.
- Run `ruff`, `mypy`, and the relevant `pytest` targets before proposing a change.

## Docs Style

- Write from `src/coryl` and the passing tests, not from intended future behavior.
- Use reproducible commands such as `python -m pip` and `python -m pytest`.
- Name the exact extra required for optional behavior.
- Be explicit about local-only, blocking, read-only, or conservative behavior.
- Mark conceptual snippets when they are illustrative rather than copy-paste runnable.
- Do not overclaim maturity. Coryl is a beta library with a well-tested local core and narrower optional boundaries.

## Adding a New Resource Type

Treat a new resource type as a public API change and keep the surface small.

1. Define the role or resource behavior in `src/coryl/resources.py`.
   Update `ResourceRole`, `ResourceSpec`, any role/kind validation, and `create_resource(...)`.
2. Wire manager registration and lookup in `src/coryl/manager.py`.
   Add namespace helpers only if the new type improves the default API enough to justify the extra surface area.
3. Decide how manifests should represent the new type.
   If manifests can declare it, update the parsing/validation path and the docs.
4. Add tests before broad docs updates.
   Cover registration, safety boundaries, read/write behavior, manifest behavior, and failure modes.
5. Update public docs and examples only when the feature is stable enough for release notes.

## Adding an Optional Integration

Optional integrations should stay optional in both packaging and code paths.

1. Add the extra in `pyproject.toml`.
   Include it in `all` only if it belongs in the public optional feature set.
2. Keep the import lazy near the usage point.
   Existing examples include `_load_pydantic_module()`, `_load_diskcache_cache_class()`, and `_load_watchfiles_watch()` in `src/coryl/resources.py`.
3. Do not add mandatory dependencies for optional features.
   The core install must keep working without the extra.
4. Add tests for both paths.
   Cover the positive path, the missing-dependency error, docs consistency, and packaged-environment behavior when needed.
5. Update `README.md`, `docs/optional-extras.md`, examples, and changelog entries so the release story stays honest.
