from __future__ import annotations

import re
from pathlib import Path

import pytest

from coryl import Coryl, CorylReadOnlyResourceError, CorylUnsafePathError


def _relative_paths(paths: list[Path], *, root: Path) -> list[str]:
    return sorted(path.relative_to(root).as_posix() for path in paths)


def test_filesystem_assets_support_registration_and_lookup_helpers(tmp_path: Path) -> None:
    app = Coryl(root=tmp_path)

    assets = app.assets.add("ui", "assets/ui")
    media = app.register_assets("media", "assets/media")

    logo = assets.file("images", "logo.svg", create=True)
    logo.write_text("<svg />")
    icons = assets.directory("icons", create=True)
    check_icon = icons.file("check.svg", create=True)
    check_icon.write_text("<svg>check</svg>")

    assert app.assets.get("ui") is assets
    assert app.assets.get("media") is media
    assert assets.require("images", "logo.svg").path == logo.path
    assert assets.require("icons", kind="directory").path == icons.path
    assert _relative_paths(assets.files("**/*"), root=tmp_path) == [
        "assets/ui/icons/check.svg",
        "assets/ui/images/logo.svg",
    ]
    assert _relative_paths(assets.glob("**/*"), root=tmp_path) == [
        "assets/ui/icons",
        "assets/ui/icons/check.svg",
        "assets/ui/images",
        "assets/ui/images/logo.svg",
    ]


def test_filesystem_asset_require_for_missing_child_raises_clear_error(tmp_path: Path) -> None:
    app = Coryl(root=tmp_path)
    assets = app.assets.add("ui", "assets/ui")
    missing_path = assets.path / "missing.txt"

    with pytest.raises(FileNotFoundError, match=re.escape(str(missing_path))):
        assets.require("missing.txt")


def test_filesystem_asset_child_path_traversal_is_rejected(tmp_path: Path) -> None:
    app = Coryl(root=tmp_path)
    assets = app.assets.add("ui", "assets/ui")

    with pytest.raises(CorylUnsafePathError, match="Path traversal"):
        assets.file("images", "..", "escape.txt")

    with pytest.raises(CorylUnsafePathError, match="Path traversal"):
        assets.directory("nested", "..", "escape")


def test_readonly_filesystem_assets_cannot_mutate(tmp_path: Path) -> None:
    logo_path = tmp_path / "assets" / "ui" / "images" / "logo.svg"
    logo_path.parent.mkdir(parents=True, exist_ok=True)
    logo_path.write_text("<svg />", encoding="utf-8")

    app = Coryl(root=tmp_path)
    assets = app.register_assets("ui", "assets/ui", readonly=True)
    logo = assets.file("images", "logo.svg")

    assert logo.readonly is True
    assert logo.read_text() == "<svg />"

    with pytest.raises(CorylReadOnlyResourceError, match="read-only"):
        logo.write_text("<svg>updated</svg>")

    with pytest.raises(CorylReadOnlyResourceError, match="read-only"):
        assets.file("images", "new.svg", create=True)

    with pytest.raises(CorylReadOnlyResourceError, match="read-only"):
        assets.directory("icons", create=True)
