from __future__ import annotations

import time
from pathlib import Path

import pytest

diskcache = pytest.importorskip("diskcache")

from coryl import (
    Coryl,
    CorylPathError,
    CorylReadOnlyResourceError,
    CorylUnsafePathError,
    DiskCacheResource,
)


def test_diskcache_registration_helpers_and_raw_backend(tmp_path: Path) -> None:
    app = Coryl(root=tmp_path)

    via_namespace = app.caches.diskcache("api", ".cache/api")
    via_add = app.caches.add("secondary", ".cache/secondary", backend="diskcache")

    assert isinstance(via_namespace, DiskCacheResource)
    assert isinstance(via_add, DiskCacheResource)
    assert via_namespace.backend == "diskcache"
    assert via_add.backend == "diskcache"
    assert isinstance(via_namespace.raw, diskcache.Cache)


def test_diskcache_set_get_load_delete_clear_and_has(tmp_path: Path) -> None:
    cache = Coryl(root=tmp_path).caches.diskcache("api", ".cache/api")

    cache.set("users/42.json", {"id": 42, "name": "Ada"})

    assert cache.has("users/42.json")
    assert cache.get("users/42.json") == {"id": 42, "name": "Ada"}
    assert cache.load("users", "42.json") == {"id": 42, "name": "Ada"}

    cache.delete("users", "42.json", missing_ok=False)

    assert not cache.has("users/42.json")

    cache.set("users/42.json", {"id": 42})
    cache.set("users/43.json", {"id": 43})
    cache.clear()

    assert not cache.has("users/42.json")
    assert not cache.has("users/43.json")


def test_diskcache_ttl_expiration_and_expire(tmp_path: Path) -> None:
    cache = Coryl(root=tmp_path).caches.diskcache("api", ".cache/api")
    cache.set("tokens/state.txt", "ready", ttl=0.001)

    time.sleep(0.02)

    removed = cache.expire()

    assert removed >= 1
    assert not cache.has("tokens/state.txt")
    assert cache.get("tokens/state.txt", default="missing") == "missing"


def test_diskcache_remember_helpers_and_memoize(tmp_path: Path) -> None:
    cache = Coryl(root=tmp_path).caches.diskcache("api", ".cache/api")
    calls = {"remember": 0, "json": 0, "text": 0, "memoize": 0}

    def build_payload() -> dict[str, object]:
        calls["remember"] += 1
        return {"call": calls["remember"]}

    def build_json_payload() -> dict[str, object]:
        calls["json"] += 1
        return {"call": calls["json"]}

    def build_text_payload() -> str:
        calls["text"] += 1
        return f"text-{calls['text']}"

    assert cache.remember("users/42.json", factory=build_payload, ttl=60) == {"call": 1}
    assert cache.remember("users/42.json", factory=build_payload, ttl=60) == {"call": 1}
    assert cache.remember_json("responses/user.json", build_json_payload, ttl=60) == {
        "call": 1
    }
    assert cache.remember_json("responses/user.json", build_json_payload, ttl=60) == {
        "call": 1
    }
    assert (
        cache.remember_text("tokens/state.txt", build_text_payload, ttl=60) == "text-1"
    )
    assert (
        cache.remember_text("tokens/state.txt", build_text_payload, ttl=60) == "text-1"
    )

    @cache.memoize(ttl=60)
    def compute(user_id: int) -> dict[str, object]:
        calls["memoize"] += 1
        return {"user_id": user_id, "calls": calls["memoize"]}

    assert compute(42) == {"user_id": 42, "calls": 1}
    assert compute(42) == {"user_id": 42, "calls": 1}
    assert calls == {"remember": 1, "json": 1, "text": 1, "memoize": 1}


def test_diskcache_rejects_unsafe_path_style_keys(tmp_path: Path) -> None:
    cache = Coryl(root=tmp_path).caches.diskcache("api", ".cache/api")

    with pytest.raises(CorylUnsafePathError):
        cache.set("../secrets.txt", "blocked")

    with pytest.raises(CorylPathError):
        cache.set(tmp_path / "secrets.txt", "blocked")

    with pytest.raises(CorylUnsafePathError):
        cache.get("../secrets.txt")

    with pytest.raises(CorylPathError):
        cache.load(tmp_path / "secrets.txt")


def test_diskcache_readonly_rejects_mutations_but_can_read(tmp_path: Path) -> None:
    writable = Coryl(root=tmp_path).caches.diskcache("api", ".cache/api")
    writable.set("users/42.json", {"id": 42})

    readonly = Coryl(root=tmp_path).caches.diskcache("api", ".cache/api", readonly=True)

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
