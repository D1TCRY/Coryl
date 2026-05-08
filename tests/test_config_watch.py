from __future__ import annotations

import pytest

import coryl.resources as coryl_resources

from coryl import Coryl, CorylOptionalDependencyError


def test_config_watch_reload_uses_watchfiles_without_real_filesystem_polling(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    watchfiles = pytest.importorskip("watchfiles")

    app = Coryl(tmp_path)
    settings = app.configs.add("settings", "config/settings.json")
    settings.save({"theme": "light"})
    calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    def fake_watch(*paths: object, **kwargs: object):
        calls.append((paths, dict(kwargs)))
        settings.save({"theme": "dark"})
        yield {("modified", str(settings.path))}

    monkeypatch.setattr(watchfiles, "watch", fake_watch)

    reloaded = next(settings.watch_reload(debounce=25))

    assert reloaded == {"theme": "dark"}
    assert calls[0][0] == (settings.path.parent,)
    assert calls[0][1]["debounce"] == 25
    assert calls[0][1]["recursive"] is False


def test_config_on_change_uses_watchfiles_callback_flow_when_available(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    watchfiles = pytest.importorskip("watchfiles")

    app = Coryl(tmp_path)
    settings = app.configs.add("settings", "config/settings.json")
    settings.save({"theme": "light"})
    seen: list[object] = []

    def fake_watch(*paths: object, **kwargs: object):
        del paths, kwargs
        settings.save({"theme": "blue"})
        yield {("modified", str(settings.path))}

    monkeypatch.setattr(watchfiles, "watch", fake_watch)

    settings.on_change(seen.append)

    assert seen == [{"theme": "blue"}]


def test_config_watch_helpers_raise_clear_optional_dependency_errors_when_missing(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_import_module = coryl_resources.import_module

    def missing_watchfiles(name: str, package: str | None = None) -> object:
        if name == "watchfiles":
            raise ModuleNotFoundError("No module named 'watchfiles'")
        return original_import_module(name, package)

    monkeypatch.setattr(coryl_resources, "import_module", missing_watchfiles)

    app = Coryl(tmp_path)
    settings = app.configs.add("settings", "config/settings.json")

    with pytest.raises(
        CorylOptionalDependencyError, match=r"pip install coryl\[watch\]"
    ):
        next(settings.watch_reload())
