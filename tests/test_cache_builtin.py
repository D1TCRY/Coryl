from __future__ import annotations

import json
from pathlib import Path

import pytest

import coryl.resources as coryl_resources

from coryl import (
    CacheResource,
    Coryl,
    CorylPathError,
    CorylReadOnlyResourceError,
    CorylUnsafePathError,
    CorylValidationError,
    Resource,
)


@pytest.fixture
def app(tmp_path: Path) -> Coryl:
    return Coryl(root=tmp_path)


@pytest.fixture
def cache(app: Coryl) -> CacheResource:
    return app.caches.add("http", ".cache/http")


@pytest.fixture
def fake_time(monkeypatch: pytest.MonkeyPatch) -> dict[str, float]:
    state = {"now": 1_000.0}
    monkeypatch.setattr(coryl_resources.time, "time", lambda: state["now"])
    return state


def _parts(path: str) -> tuple[str, ...]:
    return Path(path).parts


def test_cache_registration_and_child_helpers(app: Coryl, tmp_path: Path) -> None:
    added = app.caches.add("http", ".cache/http")
    registered = app.register_cache("api", ".cache/api")

    entry = added.entry("users", "42.json", create=True)
    file_resource = added.file("tokens", "state.txt", create=True)
    directory = added.directory("users", create=True)

    assert isinstance(added, CacheResource)
    assert isinstance(registered, CacheResource)
    assert app.caches.get("http") is added
    assert app.cache_resource("api") is registered

    assert isinstance(entry, Resource)
    assert entry.path == (tmp_path / ".cache" / "http" / "users" / "42.json").resolve()
    assert entry.path.is_relative_to(added.path)

    assert file_resource.path == (tmp_path / ".cache" / "http" / "tokens" / "state.txt").resolve()
    assert file_resource.path.is_file()
    assert file_resource.path.is_relative_to(added.path)

    assert isinstance(directory, CacheResource)
    assert directory.path == (tmp_path / ".cache" / "http" / "users").resolve()
    assert directory.path.is_dir()
    assert directory.path.is_relative_to(added.path)


@pytest.mark.parametrize(
    ("path", "value"),
    [
        ("users/42.json", {"id": 42, "name": "Ada"}),
        ("users/list.json", [{"id": 42}, {"id": 43}]),
        ("tokens/state.txt", "ready"),
        ("payload.bin", b"\x00\xffcache-bytes"),
        ("config/settings.toml", {"debug": True, "ports": [8000, 8001]}),
        ("notes/custom.cache", "opaque text"),
    ],
)
def test_cache_set_get_and_load_round_trips(
    cache: CacheResource,
    path: str,
    value: object,
) -> None:
    cache.set(path, value)

    assert cache.get(path) == value
    assert cache.load(*_parts(path)) == value

    entry = cache.file(*_parts(path))
    if isinstance(value, bytes):
        assert entry.read_bytes() == value
        return

    raw_text = entry.read_text()
    if path.endswith(".json"):
        assert json.loads(raw_text) == value
        assert "\n" in raw_text
    elif path.endswith(".toml"):
        assert entry.read_toml() == value
        assert "debug = true" in raw_text
    else:
        assert raw_text == value


def test_cache_yaml_round_trip_when_yaml_is_available(cache: CacheResource) -> None:
    pytest.importorskip("yaml")

    payload = {"theme": "light", "debug": True}
    cache.set("config/settings.yaml", payload)

    assert cache.get("config/settings.yaml") == payload
    assert cache.load("config", "settings.yaml") == payload
    assert "theme: light" in cache.file("config", "settings.yaml").read_text()


def test_cache_load_honors_expired_ttl_and_cleans_up(cache: CacheResource, fake_time: dict[str, float]) -> None:
    cache.set("tokens/state.txt", "stale", ttl=10)

    fake_time["now"] = 1_011.0

    assert cache.load("tokens", "state.txt", default="missing") == "missing"
    assert not cache.has("tokens/state.txt")
    assert not cache.file("tokens", "state.txt").exists()


def test_cache_ttl_persistence_and_expire(cache: CacheResource, fake_time: dict[str, float]) -> None:
    cache.set("tokens/persistent.txt", "keep")
    cache.set("tokens/fresh.txt", "fresh", ttl=60)
    cache.set("tokens/stale.txt", "stale", ttl=5)

    fake_time["now"] = 1_006.0

    assert cache.get("tokens/persistent.txt") == "keep"
    assert cache.get("tokens/fresh.txt") == "fresh"
    assert cache.get("tokens/stale.txt", default="missing") == "missing"

    cache.set("tokens/stale-again.txt", "stale", ttl=5)
    fake_time["now"] = 1_012.0

    removed = cache.expire()

    assert removed == 1
    assert cache.has("tokens/persistent.txt")
    assert cache.has("tokens/fresh.txt")
    assert not cache.has("tokens/stale-again.txt")


def test_cache_remember_recomputes_only_for_missing_or_expired_entries(
    cache: CacheResource,
    fake_time: dict[str, float],
) -> None:
    calls = {"remember": 0, "json": 0, "text": 0}

    def build_remember_value() -> dict[str, object]:
        calls["remember"] += 1
        return {"call": calls["remember"]}

    def build_json_value() -> dict[str, object]:
        calls["json"] += 1
        return {"call": calls["json"]}

    def build_text_value() -> str:
        calls["text"] += 1
        return f"state-{calls['text']}"

    first = cache.remember("users/42.json", factory=build_remember_value, ttl=10)
    second = cache.remember("users/42.json", factory=build_remember_value, ttl=10)
    first_json = cache.remember_json("responses/user.json", build_json_value, ttl=10)
    second_json = cache.remember_json("responses/user.json", build_json_value, ttl=10)
    first_text = cache.remember_text("tokens/state.txt", build_text_value, ttl=10)
    second_text = cache.remember_text("tokens/state.txt", build_text_value, ttl=10)

    assert first == second == {"call": 1}
    assert first_json == second_json == {"call": 1}
    assert first_text == second_text == "state-1"
    assert calls == {"remember": 1, "json": 1, "text": 1}

    fake_time["now"] = 1_011.0

    refreshed = cache.remember("users/42.json", factory=build_remember_value, ttl=10)
    refreshed_json = cache.remember_json("responses/user.json", build_json_value, ttl=10)
    refreshed_text = cache.remember_text("tokens/state.txt", build_text_value, ttl=10)

    assert refreshed == {"call": 2}
    assert refreshed_json == {"call": 2}
    assert refreshed_text == "state-2"
    assert calls == {"remember": 2, "json": 2, "text": 2}


def test_cache_legacy_multipart_remember_and_load_stay_compatible(cache: CacheResource) -> None:
    returned_path = cache.remember(
        "responses",
        "users.json",
        content={"id": 42, "name": "Ada"},
    )

    assert returned_path == cache.file("responses", "users.json").path
    assert cache.load("responses", "users.json") == {"id": 42, "name": "Ada"}

    cache.remember("responses", "users.json", content={"id": 7, "name": "Grace"})

    assert cache.load("responses", "users.json") == {"id": 7, "name": "Grace"}
    assert '"name": "Grace"' in cache.file("responses", "users.json").read_text()


def test_cache_delete_and_clear_manage_cached_entries(cache: CacheResource) -> None:
    cache.set("users/42.json", {"id": 42})
    cache.set("payload.bin", b"abc")

    cache.delete("users", "42.json", missing_ok=False)

    assert not cache.has("users/42.json")
    assert cache.has("payload.bin")

    cache.clear()

    assert list(cache.iterdir()) == []


def test_cache_rejects_reserved_traversal_absolute_and_escaping_child_paths(
    cache: CacheResource,
    tmp_path: Path,
) -> None:
    with pytest.raises(CorylValidationError, match="reserved for Coryl metadata"):
        cache.set(".coryl-cache-index.json", "blocked")

    with pytest.raises(CorylValidationError, match="reserved for Coryl metadata"):
        cache.load(".coryl-cache-index.json")

    with pytest.raises(CorylUnsafePathError):
        cache.set("../secrets.txt", "blocked")

    with pytest.raises(CorylPathError):
        cache.set(tmp_path / "secrets.txt", "blocked")

    with pytest.raises(CorylUnsafePathError):
        cache.file("nested", "..", "escape.txt")

    with pytest.raises(CorylUnsafePathError):
        cache.directory("nested", "..", "escape")

    with pytest.raises(CorylPathError):
        cache.file(tmp_path / ".cache" / "http" / "escape.txt")


def test_readonly_cache_rejects_mutations_but_can_read(tmp_path: Path) -> None:
    writable = Coryl(root=tmp_path).caches.add("http", ".cache/http")
    writable.set("users/42.json", {"id": 42})

    readonly = Coryl(root=tmp_path).register_cache("http", ".cache/http", readonly=True)

    assert readonly.load("users", "42.json") == {"id": 42}
    assert readonly.remember("users/42.json", content={"id": 7}) == {"id": 42}

    with pytest.raises(CorylReadOnlyResourceError):
        readonly.set("users/43.json", {"id": 43})

    with pytest.raises(CorylReadOnlyResourceError):
        readonly.remember("users/43.json", content={"id": 43})

    with pytest.raises(CorylReadOnlyResourceError):
        readonly.delete("users", "42.json")

    with pytest.raises(CorylReadOnlyResourceError):
        readonly.clear()

    with pytest.raises(CorylReadOnlyResourceError):
        readonly.expire()
