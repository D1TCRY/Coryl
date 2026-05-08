from __future__ import annotations

import uuid
from collections.abc import Callable
from pathlib import Path, PurePosixPath

import pytest

import coryl.manager as coryl_manager
import coryl.resources as coryl_resources
from coryl import Coryl, CorylPathError, CorylUnsafePathError, CorylValidationError

pytest.importorskip("fsspec")


def _build_with_fs(root: str) -> Coryl:
    return Coryl.with_fs(root=root, protocol="memory")


def _build_with_constructor(root: str) -> Coryl:
    return Coryl(root=root, filesystem="fsspec", protocol="memory")


def _memory_root() -> str:
    return f"memory://coryl-{uuid.uuid4().hex}"


def _relative_paths(paths: list[PurePosixPath], root: PurePosixPath) -> set[str]:
    return {path.relative_to(root).as_posix() for path in paths}


@pytest.fixture(params=[_build_with_fs, _build_with_constructor], ids=["with-fs", "filesystem-arg"])
def memory_app(request: pytest.FixtureRequest) -> Coryl:
    builder = request.param
    return builder(_memory_root())


def test_fsspec_construction_supports_both_documented_entry_points(memory_app: Coryl) -> None:
    assert isinstance(memory_app.root_path, PurePosixPath)
    assert memory_app.root_path.is_absolute()
    assert memory_app.root_path.name.startswith("coryl-")


def test_fsspec_memory_backend_supports_basic_resources_and_io(memory_app: Coryl) -> None:
    notes = memory_app.register_file("notes", "data/notes.txt", create=False)
    blob = memory_app.register_file("blob", "data/blob.bin", create=False)
    state = memory_app.register_file("state", "data/state.json", create=False)
    app_toml = memory_app.register_file("app_toml", "config/app.toml", create=False)
    settings = memory_app.register_config("settings", "config/settings.json", create=False)
    exports = memory_app.register_directory("exports", "build/exports", create=False)

    assert notes.exists() is False
    assert exports.exists() is False

    notes.ensure()
    exports.ensure()

    assert notes.exists() is True
    assert notes.is_file() is True
    assert exports.exists() is True
    assert exports.is_dir() is True

    notes.write_text("hello from fsspec")
    blob.write_bytes(b"\x00\x01coryl")
    state.write_json({"enabled": True, "count": 2})
    app_toml.write_toml({"theme": "light", "debug": False})
    settings.save({"name": "Coryl", "enabled": True})

    assert notes.read_text() == "hello from fsspec"
    assert blob.read_bytes() == b"\x00\x01coryl"
    assert state.read_json() == {"enabled": True, "count": 2}
    assert app_toml.read_toml() == {"theme": "light", "debug": False}
    assert settings.load() == {"name": "Coryl", "enabled": True}


def test_fsspec_yaml_helpers_work_when_yaml_is_available(memory_app: Coryl) -> None:
    pytest.importorskip("yaml")

    settings = memory_app.register_file("settings_yaml", "config/settings.yaml", create=False)

    settings.write_yaml({"theme": "dark", "enabled": True})

    assert settings.read_yaml() == {"theme": "dark", "enabled": True}


def test_fsspec_memory_backend_supports_builtin_cache_helpers(memory_app: Coryl) -> None:
    cache = memory_app.register_cache("http", ".cache/http", create=False)
    json_calls = 0
    text_calls = 0

    def build_user() -> dict[str, object]:
        nonlocal json_calls
        json_calls += 1
        return {"id": 42, "name": "Ada"}

    def build_etag() -> str:
        nonlocal text_calls
        text_calls += 1
        return "etag-v1"

    assert cache.exists() is False

    cache.ensure()
    cache.set("payload.bin", b"\x00cache")

    first_user = cache.remember_json("users/42.json", build_user)
    second_user = cache.remember_json("users/42.json", build_user)
    first_etag = cache.remember_text("headers/etag.txt", build_etag)
    second_etag = cache.remember_text("headers/etag.txt", build_etag)

    assert cache.exists() is True
    assert cache.is_dir() is True
    assert cache.get("payload.bin") == b"\x00cache"
    assert cache.load("users/42.json") == {"id": 42, "name": "Ada"}
    assert cache.has("users/42.json") is True
    assert first_user == second_user == {"id": 42, "name": "Ada"}
    assert first_etag == second_etag == "etag-v1"
    assert json_calls == 1
    assert text_calls == 1


def test_fsspec_directory_glob_and_asset_files_work(memory_app: Coryl) -> None:
    assets = memory_app.register_assets("assets", "assets", create=False)
    logo = assets.file("images", "logo.txt", create=True)
    settings = assets.file("config", "settings.json", create=True)

    logo.write_text("logo")
    settings.write_json({"theme": "light"})

    assert _relative_paths(assets.glob("**/*"), assets.path) == {
        "config",
        "config/settings.json",
        "images",
        "images/logo.txt",
    }
    assert _relative_paths(assets.files("**/*"), assets.path) == {
        "config/settings.json",
        "images/logo.txt",
    }


@pytest.mark.parametrize(
    ("path_factory", "expected_error"),
    [
        pytest.param(lambda _tmp_path: "../escape.txt", CorylUnsafePathError, id="traversal"),
        pytest.param(lambda _tmp_path: "/escape.txt", CorylPathError, id="absolute-posix"),
        pytest.param(lambda tmp_path: tmp_path / "escape.txt", CorylPathError, id="absolute-local"),
        pytest.param(
            lambda _tmp_path: "memory://elsewhere/escape.txt",
            CorylPathError,
            id="foreign-uri",
        ),
    ],
)
def test_fsspec_registration_rejects_unsafe_paths(
    memory_app: Coryl,
    tmp_path: Path,
    path_factory: Callable[[Path], str | Path],
    expected_error: type[Exception],
) -> None:
    with pytest.raises(expected_error):
        memory_app.register_file("unsafe", path_factory(tmp_path))


@pytest.mark.parametrize(
    ("parts", "expected_error"),
    [
        pytest.param(("..", "escape.txt"), CorylUnsafePathError, id="traversal"),
        pytest.param(("/escape.txt",), CorylPathError, id="absolute-posix"),
        pytest.param(
            ("memory://elsewhere/escape.txt",),
            CorylPathError,
            id="foreign-uri",
        ),
    ],
)
def test_fsspec_child_resources_cannot_escape_the_parent(
    memory_app: Coryl,
    parts: tuple[str, ...],
    expected_error: type[Exception],
) -> None:
    assets = memory_app.register_assets("assets", "assets")

    with pytest.raises(expected_error):
        assets.file(*parts)


def test_fsspec_child_resources_reject_local_absolute_paths(memory_app: Coryl, tmp_path: Path) -> None:
    assets = memory_app.register_assets("assets", "assets")

    with pytest.raises(CorylPathError):
        assets.file(tmp_path / "escape.txt")


def test_fsspec_atomic_writes_fall_back_to_regular_writes(
    memory_app: Coryl,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    notes = memory_app.register_file("notes", "data/notes.txt", create=False)
    blob = memory_app.register_file("blob", "data/blob.bin", create=False)
    settings = memory_app.register_config("settings", "config/settings.toml", create=False)

    def fail_atomic(*args: object, **kwargs: object) -> PurePosixPath:
        del args, kwargs
        raise AssertionError("local atomic helpers should not run for fsspec-backed resources")

    monkeypatch.setattr(coryl_resources, "_atomic_write_text", fail_atomic)
    monkeypatch.setattr(coryl_resources, "_atomic_write_bytes", fail_atomic)

    notes.write_text("non-atomic text")
    blob.write_bytes(b"\x01\x02")
    settings.save({"enabled": True})

    assert notes.read_text() == "non-atomic text"
    assert blob.read_bytes() == b"\x01\x02"
    assert settings.load() == {"enabled": True}


def test_fsspec_lock_and_watch_remain_local_only(memory_app: Coryl) -> None:
    notes = memory_app.register_file("notes", "data/notes.txt")

    with pytest.raises(CorylValidationError, match="default local filesystem"):
        with notes.lock():
            raise AssertionError("lock() should not enter on fsspec backends")

    with pytest.raises(CorylValidationError, match="default local filesystem"):
        next(notes.watch(yield_on_timeout=True))


def test_fsspec_diskcache_backend_is_local_only(
    memory_app: Coryl,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_dependency_load() -> object:
        raise AssertionError("diskcache should not be imported for fsspec-backed managers")

    monkeypatch.setattr(coryl_manager, "_load_diskcache_cache_class", fail_dependency_load)

    with pytest.raises(
        CorylValidationError,
        match="The diskcache backend is only supported on the default local filesystem.",
    ):
        memory_app.register_cache("disk", ".cache/disk", backend="diskcache")

    with pytest.raises(
        CorylValidationError,
        match="The diskcache backend is only supported on the default local filesystem.",
    ):
        memory_app.caches.diskcache("disk-namespace", ".cache/disk-namespace")


def test_fsspec_layered_config_registration_is_local_only(memory_app: Coryl) -> None:
    with pytest.raises(CorylValidationError, match="register_layered_config\\(\\) currently requires"):
        memory_app.register_layered_config(
            "settings",
            files=["config/defaults.toml", "config/local.toml"],
        )
