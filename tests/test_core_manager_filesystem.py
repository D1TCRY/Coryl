from __future__ import annotations

from pathlib import Path

import pytest

from coryl import Coryl, ResourceKindError, ResourceNotRegisteredError


def test_create_missing_true_creates_registered_resources(tmp_path: Path) -> None:
    app = Coryl(root=tmp_path, create_missing=True)

    notes = app.register_file("notes", "data/notes.txt")
    exports = app.register_directory("exports", "build/exports")

    assert notes.exists()
    assert notes.is_file()
    assert exports.exists()
    assert exports.is_dir()


def test_create_missing_false_leaves_registered_resources_absent_until_written(
    tmp_path: Path,
) -> None:
    app = Coryl(root=tmp_path, create_missing=False)

    settings = app.register_file("settings", "config/settings.json")
    assets = app.register_directory("assets", "assets/ui")

    assert not settings.exists()
    assert not assets.exists()

    app.write_content("settings", {"enabled": True})

    assert settings.exists()
    assert settings.read_json() == {"enabled": True}
    assert settings.path.parent.is_dir()
    assert not assets.exists()


def test_manager_helpers_cover_resource_lookup_and_content_io(tmp_path: Path) -> None:
    app = Coryl(root=tmp_path)

    state = app.register_file("state", "data/state.json")
    logs = app.register_directory("logs", "runtime/logs")

    returned_path = app.write_content("state", {"count": 1})

    assert returned_path == state.path
    assert app.resource("state") is state
    assert app.resource("logs") is logs
    assert app.file("state") is state
    assert app.directory("logs") is logs
    assert app.path("state") == state.path
    assert app.content("state") == {"count": 1}


def test_manager_lookup_errors_use_specific_coryl_exceptions(tmp_path: Path) -> None:
    app = Coryl(root=tmp_path)
    app.register_directory("assets", "assets")

    with pytest.raises(ResourceNotRegisteredError):
        app.resource("missing")

    with pytest.raises(ResourceKindError):
        app.file("assets")
