from __future__ import annotations

import json
from pathlib import Path

import pytest

from coryl import Coryl, CorylUnsupportedFormatError

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.10 fallback
    import tomli as tomllib


def test_json_read_write_round_trip(tmp_path: Path) -> None:
    app = Coryl(root=tmp_path)
    settings = app.register_file("settings", "config/settings.json")
    payload = {"name": "Coryl", "enabled": True, "ports": [8000, 8001]}

    settings.write_json(payload)

    assert settings.read_json() == payload
    assert app.content("settings") == payload


def test_toml_read_write_round_trip(tmp_path: Path) -> None:
    app = Coryl(root=tmp_path)
    settings = app.register_file("settings", "config/settings.toml")
    payload = {
        "name": "Coryl",
        "enabled": True,
        "database": {"host": "localhost", "port": 5432},
    }

    settings.write_toml(payload)

    assert settings.read_toml() == payload


def test_yaml_read_write_round_trip_when_yaml_support_is_installed(
    tmp_path: Path,
) -> None:
    pytest.importorskip("yaml")
    app = Coryl(root=tmp_path)
    settings = app.register_file("settings", "config/settings.yaml")
    payload = {"theme": "dark", "language": "en", "features": ["safe", "local"]}

    settings.write_yaml(payload)

    assert settings.read_yaml() == payload


def test_unsupported_structured_format_raises_clear_error(tmp_path: Path) -> None:
    app = Coryl(root=tmp_path)
    notes = app.register_file("notes", "notes.txt")

    with pytest.raises(CorylUnsupportedFormatError, match="Supported formats are"):
        notes.read_data()

    with pytest.raises(CorylUnsupportedFormatError, match="Supported formats are"):
        notes.write_data({"message": "hello"})


def test_invalid_json_content_raises_clear_error(tmp_path: Path) -> None:
    app = Coryl(root=tmp_path, create_missing=False)
    settings = app.register_file("settings", "config/settings.json")
    settings.path.parent.mkdir(parents=True, exist_ok=True)
    settings.path.write_text('{"broken": ', encoding="utf-8")

    with pytest.raises(json.JSONDecodeError) as caught:
        settings.read_json()

    assert "Expecting value" in str(caught.value)


def test_invalid_toml_content_raises_clear_error(tmp_path: Path) -> None:
    app = Coryl(root=tmp_path, create_missing=False)
    settings = app.register_file("settings", "config/settings.toml")
    settings.path.parent.mkdir(parents=True, exist_ok=True)
    settings.path.write_text('title = "broken"\n[section\n', encoding="utf-8")

    with pytest.raises(tomllib.TOMLDecodeError) as caught:
        settings.read_toml()

    assert str(caught.value)
