from __future__ import annotations

import tomllib
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
README_PATH = PROJECT_ROOT / "README.md"
EXAMPLES_README_PATH = PROJECT_ROOT / "examples" / "README.md"
OPTIONAL_EXTRAS_PATH = PROJECT_ROOT / "docs" / "optional-extras.md"
MATRIX_PATH = PROJECT_ROOT / "docs" / "DOCUMENTATION_MATRIX.md"
PYPROJECT_PATH = PROJECT_ROOT / "pyproject.toml"
EXAMPLE_SCRIPTS = sorted(
    path.name
    for path in (PROJECT_ROOT / "examples").glob("*.py")
    if not path.name.startswith("_")
)


def test_root_readme_and_examples_readme_list_every_example_script() -> None:
    readme = README_PATH.read_text(encoding="utf-8")
    examples_readme = EXAMPLES_README_PATH.read_text(encoding="utf-8")

    for script_name in EXAMPLE_SCRIPTS:
        assert script_name in readme
        assert script_name in examples_readme


def test_readme_and_optional_extras_doc_cover_declared_optional_extras() -> None:
    pyproject = tomllib.loads(PYPROJECT_PATH.read_text(encoding="utf-8"))
    declared_extras = sorted(pyproject["project"]["optional-dependencies"])
    readme = README_PATH.read_text(encoding="utf-8")
    optional_extras_doc = OPTIONAL_EXTRAS_PATH.read_text(encoding="utf-8")

    for extra in declared_extras:
        install_hint = f"coryl[{extra}]"
        assert install_hint in readme
        assert install_hint in optional_extras_doc


def test_documentation_matrix_exists_and_mentions_examples() -> None:
    matrix = MATRIX_PATH.read_text(encoding="utf-8")

    assert "## Feature Matrix" in matrix
    assert "## README Code Block Coverage" in matrix
    for script_name in EXAMPLE_SCRIPTS:
        assert script_name in matrix
