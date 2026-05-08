from __future__ import annotations

import importlib
import re
import sys
import zipfile
from collections.abc import Iterator
from pathlib import Path

import pytest

from coryl import (
    Coryl,
    CorylPathError,
    CorylReadOnlyResourceError,
    CorylUnsafePathError,
    PackageAssetGroup,
    PackageAssetResource,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_IMPORT_ROOT = PROJECT_ROOT / "tests" / "fixtures" / "package_assets_fixture"
FIXTURE_PACKAGE_NAME = "coryl_asset_fixture_pkg"


def _clear_package(package_name: str) -> None:
    for module_name in list(sys.modules):
        if module_name == package_name or module_name.startswith(f"{package_name}."):
            sys.modules.pop(module_name, None)


def _build_fixture_zip(source_root: Path, destination: Path) -> None:
    with zipfile.ZipFile(destination, "w") as archive:
        for path in sorted(source_root.rglob("*")):
            if path.is_dir():
                continue
            archive.write(path, path.relative_to(source_root))


@pytest.fixture(params=["directory", "zip"], ids=["directory-package", "zip-package"])
def fixture_package_name(
    request: pytest.FixtureRequest,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> Iterator[str]:
    _clear_package(FIXTURE_PACKAGE_NAME)
    importlib.invalidate_caches()

    if request.param == "directory":
        monkeypatch.syspath_prepend(str(FIXTURE_IMPORT_ROOT))
    else:
        zip_path = tmp_path / "fixture-package.zip"
        _build_fixture_zip(FIXTURE_IMPORT_ROOT, zip_path)
        monkeypatch.syspath_prepend(str(zip_path))

    importlib.invalidate_caches()
    try:
        yield FIXTURE_PACKAGE_NAME
    finally:
        _clear_package(FIXTURE_PACKAGE_NAME)
        importlib.invalidate_caches()


def test_register_package_assets_reads_resources_across_import_styles(
    tmp_path: Path,
    fixture_package_name: str,
) -> None:
    app = Coryl(root=tmp_path)

    assets = app.register_package_assets("bundled", fixture_package_name, "assets")

    assert isinstance(assets, PackageAssetGroup)
    assert app.assets.get("bundled") is assets
    assert assets.readonly is True
    assert (
        assets.read_text("templates", "email.html") == "<html>Hello from Coryl</html>"
    )
    assert assets.read_bytes("images", "logo.bin") == b"\x00\x01coryl"
    assert assets.exists("nested", "docs", "readme.txt") is True
    assert assets.exists("missing.txt") is False


def test_from_package_supports_default_root_and_file_materialization(
    tmp_path: Path,
    fixture_package_name: str,
) -> None:
    app = Coryl(root=tmp_path)

    assets = app.assets.from_package("fixture_root", fixture_package_name)
    template = assets.file("assets", "templates", "email.html")

    assert isinstance(template, PackageAssetResource)
    assert (
        assets.read_text("assets", "templates", "email.html")
        == "<html>Hello from Coryl</html>"
    )
    assert assets.read_bytes("assets", "images", "logo.bin") == b"\x00\x01coryl"

    with template.as_file() as materialized_path:
        assert materialized_path.is_file()
        assert (
            materialized_path.read_text(encoding="utf-8")
            == "<html>Hello from Coryl</html>"
        )


def test_package_asset_namespace_alias_and_files_listing(
    tmp_path: Path,
    fixture_package_name: str,
) -> None:
    app = Coryl(root=tmp_path)

    assets = app.assets.package("bundled", fixture_package_name, "assets")
    nested = assets.require("nested", kind="directory")
    matched = assets.files("**/*")

    assert isinstance(nested, PackageAssetGroup)
    assert [resource.relative_path.as_posix() for resource in matched] == [
        "images/logo.bin",
        "nested/docs/readme.txt",
        "templates/email.html",
    ]
    assert [
        resource.relative_path.as_posix() for resource in assets.files("**/*.html")
    ] == [
        "templates/email.html",
    ]


def test_package_asset_require_missing_and_traversal_errors_are_clear(
    tmp_path: Path,
    fixture_package_name: str,
) -> None:
    app = Coryl(root=tmp_path)
    assets = app.assets.from_package("bundled", fixture_package_name, "assets")

    with pytest.raises(
        FileNotFoundError,
        match=re.escape(f"package://{fixture_package_name}/assets/missing.txt"),
    ):
        assets.require("missing.txt")

    with pytest.raises(CorylUnsafePathError, match="Path traversal"):
        assets.file("..", "escape.txt")


def test_package_assets_are_readonly_by_default(
    tmp_path: Path, fixture_package_name: str
) -> None:
    app = Coryl(root=tmp_path)
    assets = app.assets.from_package("bundled", fixture_package_name, "assets")
    template = assets.file("templates", "email.html")

    assert assets.readonly is True
    assert template.readonly is True

    with pytest.raises(CorylReadOnlyResourceError, match="read-only"):
        template.write_text("updated")

    with pytest.raises(CorylReadOnlyResourceError, match="read-only"):
        assets.file("new.txt", create=True)

    with pytest.raises(CorylReadOnlyResourceError, match="read-only"):
        assets.directory("new-dir", create=True)

    with pytest.raises(CorylPathError, match="stable filesystem path"):
        _ = assets.path


def test_package_assets_copy_to_overwrite_and_target_safety(
    tmp_path: Path,
    fixture_package_name: str,
) -> None:
    app = Coryl(root=tmp_path)
    assets = app.assets.from_package("bundled", fixture_package_name, "assets")
    target = tmp_path / "bootstrap"

    (target / "templates").mkdir(parents=True, exist_ok=True)
    (target / "templates" / "email.html").write_text("stale", encoding="utf-8")

    with pytest.raises(
        FileExistsError, match=re.escape(str(target / "templates" / "email.html"))
    ):
        assets.copy_to(target)

    copied_root = assets.copy_to(target, overwrite=True)

    assert copied_root == target.resolve()
    assert (copied_root / "templates" / "email.html").read_text(encoding="utf-8") == (
        "<html>Hello from Coryl</html>"
    )
    assert (copied_root / "images" / "logo.bin").read_bytes() == b"\x00\x01coryl"
    assert (copied_root / "nested" / "docs" / "readme.txt").read_text(
        encoding="utf-8"
    ) == ("Nested package asset")

    unsafe_target = tmp_path / "exports" / ".." / "escape"
    with pytest.raises(CorylUnsafePathError, match="Path traversal"):
        assets.copy_to(unsafe_target)
