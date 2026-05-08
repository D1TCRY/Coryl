# AGENTS

This file is for coding agents and automated contributors working in this repository.

## Setup Commands

```bash
python -m venv .venv
# PowerShell
.venv\Scripts\Activate.ps1
# bash/zsh
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
python -m pip install pytest pytest-cov mypy "ruff>=0.11" tox build twine
```

Install optional integrations only when the task needs them:

```bash
python -m pip install -e ".[all]"
```

## Test Commands

Run the smallest relevant command that still covers the change:

```bash
python -m pytest -q
python -m pytest -q tests/test_documentation_consistency.py tests/test_release_readiness.py
python -m pytest -q tests/test_examples.py
python -m tox -q
python -m build --sdist --wheel
python -m twine check dist/*
python -m ruff check .
python -m ruff format --check .
python -m mypy -p coryl
```

## Style Rules

- Keep Coryl simple by default.
- Do not add mandatory dependencies for optional features.
- Preserve lazy optional imports and clear `CorylOptionalDependencyError` install hints.
- Prefer explicit local-resource behavior over hidden framework-style indirection.
- Treat docs and examples as release-facing code: update them when public behavior changes.
- Be honest about limitations, especially for beta maturity, local-only helpers, and conservative `fsspec` support.

## Working Rules

- Prefer tests before feature changes.
- If you touch packaging metadata, README install text, or release-facing docs, run build and `twine check`.
- If you touch optional behavior, run the focused tests for that extra or `tox`.
- Avoid broad refactors unless they are required to keep the public API coherent.
- Keep wheels runtime-minimal and keep contributor docs available in the sdist.

## Before Final Response

- Run relevant tests before final response.
- Mention any checks you could not run.
- Call out remaining documentation or packaging risks instead of smoothing them over.
