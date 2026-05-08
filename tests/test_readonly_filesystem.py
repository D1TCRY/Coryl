from __future__ import annotations

import json
from pathlib import Path

import pytest

from coryl import Coryl, CorylReadOnlyResourceError


def test_readonly_file_cannot_write_but_can_still_read(tmp_path: Path) -> None:
    file_path = tmp_path / "data" / "notes.txt"
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text("hello", encoding="utf-8")

    app = Coryl(root=tmp_path)
    notes = app.register_file("notes", "data/notes.txt", readonly=True)

    assert notes.read_text() == "hello"
    assert app.content("notes") == "hello"

    with pytest.raises(CorylReadOnlyResourceError):
        notes.write_text("updated")

    with pytest.raises(CorylReadOnlyResourceError):
        app.write_content("notes", "updated")


def test_readonly_directory_cannot_create_child_write_target(tmp_path: Path) -> None:
    existing_file = tmp_path / "assets" / "logo.txt"
    existing_file.parent.mkdir(parents=True, exist_ok=True)
    existing_file.write_text("logo", encoding="utf-8")

    app = Coryl(root=tmp_path)
    assets = app.register_directory("assets", "assets", readonly=True)
    logo = assets.joinpath("logo.txt", kind="file")

    assert logo.read_text() == "logo"

    with pytest.raises(CorylReadOnlyResourceError):
        assets.joinpath("new.txt", kind="file", create=True)


def test_readonly_config_cannot_save_update_or_migrate_but_can_load(tmp_path: Path) -> None:
    config_path = tmp_path / "config" / "settings.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        json.dumps({"version": 1, "theme": "light"}) + "\n",
        encoding="utf-8",
    )

    app = Coryl(root=tmp_path)
    settings = app.register_config(
        "settings",
        "config/settings.json",
        readonly=True,
        version=2,
    )

    @settings.migration(from_version=1, to_version=2)
    def _migrate(document: dict[str, object]) -> dict[str, object]:
        document["theme"] = "dark"
        return document

    assert settings.load() == {"version": 1, "theme": "light"}

    with pytest.raises(CorylReadOnlyResourceError):
        settings.save({"theme": "dark"})

    with pytest.raises(CorylReadOnlyResourceError):
        settings.update(theme="dark")

    with pytest.raises(CorylReadOnlyResourceError):
        settings.migrate()


def test_readonly_cache_cannot_mutate_but_can_read(tmp_path: Path) -> None:
    cache_file = tmp_path / ".cache" / "http" / "users" / "42.json"
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache_file.write_text('{"id": 42}\n', encoding="utf-8")

    app = Coryl(root=tmp_path)
    cache = app.register_cache("http_cache", ".cache/http", readonly=True)

    assert cache.load("users", "42.json") == {"id": 42}

    with pytest.raises(CorylReadOnlyResourceError):
        cache.set("users/43.json", {"id": 43})

    with pytest.raises(CorylReadOnlyResourceError):
        cache.delete("users", "42.json")

    with pytest.raises(CorylReadOnlyResourceError):
        cache.clear()


def test_readonly_assets_cannot_mutate_but_can_read(tmp_path: Path) -> None:
    logo_path = tmp_path / "assets" / "ui" / "logo.svg"
    logo_path.parent.mkdir(parents=True, exist_ok=True)
    logo_path.write_text("<svg />", encoding="utf-8")

    app = Coryl(root=tmp_path)
    assets = app.register_assets("ui", "assets/ui", readonly=True)
    logo = assets.file("logo.svg")

    assert logo.read_text() == "<svg />"
    assert assets.require("logo.svg").path == logo.path

    with pytest.raises(CorylReadOnlyResourceError):
        logo.write_text("<svg>updated</svg>")

    with pytest.raises(CorylReadOnlyResourceError):
        assets.file("new.svg", create=True)

    with pytest.raises(CorylReadOnlyResourceError):
        assets.directory("icons", create=True)
