from __future__ import annotations

import inspect
from pathlib import Path

import pytest

import coryl._io as coryl_io
import coryl.resources as coryl_resources
from coryl import ConfigResource, Coryl, Resource


def _temporary_files_for(destination: Path) -> list[Path]:
    prefix = f".{destination.name}."
    return sorted(
        candidate
        for candidate in destination.parent.iterdir()
        if candidate.name.startswith(prefix) and candidate.name.endswith(".tmp")
    )


WRITE_CASES = [
    pytest.param("data/notes.txt", "write_text", "read_text", "daily summary", id="text"),
    pytest.param("data/archive.bin", "write_bytes", "read_bytes", b"\x00\x01coryl", id="bytes"),
    pytest.param("data/state.json", "write_json", "read_json", {"count": 1}, id="json"),
    pytest.param(
        "config/settings.toml",
        "write_toml",
        "read_toml",
        {"theme": "dark", "enabled": True},
        id="toml",
    ),
    pytest.param(
        "config/settings.yaml",
        "write_yaml",
        "read_yaml",
        {"theme": "dark", "enabled": True},
        id="yaml",
    ),
]


@pytest.mark.parametrize(("relative_path", "writer_name", "reader_name", "payload"), WRITE_CASES)
def test_write_helpers_save_expected_data_and_clean_up_temp_files(
    tmp_path: Path,
    relative_path: str,
    writer_name: str,
    reader_name: str,
    payload: object,
) -> None:
    if reader_name == "read_yaml":
        pytest.importorskip("yaml")

    app = Coryl(root=tmp_path, create_missing=False)
    resource = app.register_file("resource", relative_path, create=False)

    getattr(resource, writer_name)(payload)

    assert resource.path.exists()
    assert resource.path.parent.is_dir()
    assert getattr(resource, reader_name)() == payload
    assert _temporary_files_for(resource.path) == []


@pytest.mark.parametrize(
    "resource_class,method_name",
    [
        pytest.param(Resource, "write_text", id="resource-write-text"),
        pytest.param(Resource, "write_bytes", id="resource-write-bytes"),
        pytest.param(Resource, "write_json", id="resource-write-json"),
        pytest.param(Resource, "write_toml", id="resource-write-toml"),
        pytest.param(Resource, "write_yaml", id="resource-write-yaml"),
        pytest.param(ConfigResource, "save", id="config-save"),
    ],
)
def test_atomic_argument_defaults_to_true(resource_class: type[object], method_name: str) -> None:
    method = getattr(resource_class, method_name)

    assert inspect.signature(method).parameters["atomic"].default is True


def test_atomic_false_uses_the_non_atomic_write_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    app = Coryl(root=tmp_path, create_missing=False)
    resource = app.register_file("notes", "data/notes.txt", create=False)

    def fail_atomic_write(*args: object, **kwargs: object) -> Path:
        raise AssertionError("atomic helper should not run when atomic=False")

    monkeypatch.setattr(coryl_resources, "_atomic_write_text", fail_atomic_write)

    resource.write_text("non-atomic text", atomic=False)

    assert resource.read_text() == "non-atomic text"


def test_atomic_false_also_works_for_structured_writes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = Coryl(root=tmp_path, create_missing=False)
    resource = app.register_file("settings", "config/settings.json", create=False)

    def fail_atomic_write(*args: object, **kwargs: object) -> Path:
        raise AssertionError("atomic helper should not run when atomic=False")

    monkeypatch.setattr(coryl_resources, "_atomic_write_text", fail_atomic_write)

    resource.write_json({"enabled": True}, atomic=False)

    assert resource.read_json() == {"enabled": True}


def test_failed_atomic_write_preserves_existing_target_and_cleans_temp_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = Coryl(root=tmp_path)
    resource = app.register_file("notes", "data/notes.txt")
    resource.write_text("before")

    temp_paths: list[Path] = []
    original_temporary_path_for = coryl_io._temporary_path_for

    def tracking_temporary_path(destination: Path) -> Path:
        temp_path = original_temporary_path_for(destination)
        temp_paths.append(temp_path)
        return temp_path

    def fail_replace(source: str | Path, destination: str | Path) -> None:
        del source, destination
        raise OSError("simulated replace failure")

    monkeypatch.setattr(coryl_io, "_temporary_path_for", tracking_temporary_path)
    monkeypatch.setattr(coryl_io.os, "replace", fail_replace)

    with pytest.raises(OSError, match="simulated replace failure"):
        resource.write_text("after")

    assert resource.read_text() == "before"
    assert temp_paths
    assert all(not temp_path.exists() for temp_path in temp_paths)
    assert _temporary_files_for(resource.path) == []
