from __future__ import annotations

from pathlib import Path

import pytest

from coryl import Coryl, MANIFEST_VERSION


def test_legacy_path_aliases_and_dynamic_helpers(tmp_path: Path) -> None:
    app = Coryl(root=tmp_path)
    config = app.register_file("config", "config/app.json")
    settings = app.register_file("settings", "config/settings.json")
    assets = app.register_directory("assets", "assets")

    assert app.root_folder_path == app.root_path
    assert app.config_file_path == config.path
    assert app.settings_file_path == settings.path
    assert app.assets_directory_path == assets.path

    with pytest.raises(AttributeError):
        _ = app.settings_directory_path

    with pytest.raises(AttributeError):
        _ = app.assets_file_path


def test_manifest_compatibility_helpers_reload_the_manifest_file(tmp_path: Path) -> None:
    manifest_path = tmp_path / "app.toml"
    manifest_path.write_text(
        (
            f"version = {MANIFEST_VERSION}\n\n"
            "[resources.settings]\n"
            'path = "config/settings.toml"\n'
            'kind = "file"\n'
            'role = "config"\n'
            "create = false\n"
        ),
        encoding="utf-8",
    )

    app = Coryl(root=tmp_path, manifest_path="app.toml")

    assert app.config_file_path == manifest_path.resolve()
    assert app.config["version"] == MANIFEST_VERSION
    assert "settings" in app.resources

    manifest_path.write_text(
        (
            f"version = {MANIFEST_VERSION}\n\n"
            "[resources.settings]\n"
            'path = "config/settings.toml"\n'
            'kind = "file"\n'
            'role = "config"\n'
            "create = false\n\n"
            "[resources.assets]\n"
            'path = "assets/ui"\n'
            'kind = "directory"\n'
            'role = "assets"\n'
            "create = false\n"
        ),
        encoding="utf-8",
    )

    reloaded_manifest = app.load_config()

    assert reloaded_manifest["resources"]["assets"]["path"] == "assets/ui"
    assert app.config["resources"]["assets"]["path"] == "assets/ui"
    assert app.assets_directory_path == (tmp_path / "assets" / "ui").resolve()
