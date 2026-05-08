from __future__ import annotations

from textwrap import dedent
from unittest import mock

import pytest

import coryl.resources as coryl_resources

from coryl import Coryl, CorylReadOnlyResourceError, CorylValidationError


def _write_text(path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dedent(content).strip() + "\n", encoding="utf-8")


def test_config_migration_requires_a_top_level_version_field(tmp_path) -> None:
    app = Coryl(tmp_path)
    settings = app.configs.add("settings", "config/settings.toml", version=2)
    settings.save({"theme": "light"})

    with pytest.raises(CorylValidationError, match="top-level integer 'version'"):
        settings.migrate()


def test_config_migration_supports_one_step_and_multi_step_flows(tmp_path) -> None:
    app = Coryl(tmp_path)

    one_step = app.configs.add("one_step", "config/one-step.toml", version=2)
    one_step.save({"version": 1, "theme": "light"})

    @one_step.migration(from_version=1, to_version=2)
    def migrate_one_step(document: dict[str, object]) -> dict[str, object]:
        document["appearance"] = {"theme": document.pop("theme")}
        return document

    assert one_step.migrate() == {"version": 2, "appearance": {"theme": "light"}}

    multi_step = app.configs.add("multi_step", "config/multi-step.toml", version=3)
    multi_step.save({"version": 1, "theme": "light"})

    @multi_step.migration(from_version=1, to_version=2)
    def migrate_to_v2(document: dict[str, object]) -> dict[str, object]:
        document["appearance"] = {"theme": document.pop("theme")}
        return document

    @multi_step.migration(from_version=2, to_version=3)
    def migrate_to_v3(document: dict[str, object]) -> dict[str, object]:
        document.setdefault("appearance", {})["mode"] = "system"
        return document

    assert multi_step.migrate() == {
        "version": 3,
        "appearance": {"theme": "light", "mode": "system"},
    }


def test_config_migration_missing_path_raises_clear_error(tmp_path) -> None:
    app = Coryl(tmp_path)
    settings = app.configs.add("settings", "config/settings.toml", version=3)
    settings.save({"version": 1, "theme": "light"})

    @settings.migration(from_version=1, to_version=2)
    def migrate_to_v2(document: dict[str, object]) -> dict[str, object]:
        document["appearance"] = {"theme": document.pop("theme")}
        return document

    with pytest.raises(CorylValidationError, match="No migration registered"):
        settings.migrate()


def test_config_migration_saves_atomically_and_skips_rewrite_when_already_current(
    tmp_path,
) -> None:
    app = Coryl(tmp_path)

    migrates = app.configs.add("migrates", "config/migrates.toml", version=2)
    migrates.save({"version": 1, "theme": "light"})

    @migrates.migration(from_version=1, to_version=2)
    def migrate_to_v2(document: dict[str, object]) -> dict[str, object]:
        document["appearance"] = {"theme": document.pop("theme")}
        return document

    with mock.patch.object(
        coryl_resources,
        "_atomic_write_text",
        wraps=coryl_resources._atomic_write_text,
    ) as atomic_write:
        migrated = migrates.migrate()

    atomic_write.assert_called_once()
    assert migrated == {"version": 2, "appearance": {"theme": "light"}}

    current = app.configs.add("current", "config/current.toml", version=2)
    current.save({"version": 2, "theme": "light"})

    with mock.patch.object(
        coryl_resources,
        "_atomic_write_text",
        wraps=coryl_resources._atomic_write_text,
    ) as atomic_write:
        migrated = current.migrate()

    atomic_write.assert_not_called()
    assert migrated == {"version": 2, "theme": "light"}


def test_config_migration_rejects_readonly_targets_and_invalid_return_values(
    tmp_path,
) -> None:
    readonly_path = tmp_path / "config" / "readonly.toml"
    _write_text(
        readonly_path,
        """
        version = 1
        theme = "light"
        """,
    )

    app = Coryl(tmp_path)
    readonly = app.register_config(
        "readonly", "config/readonly.toml", readonly=True, version=2
    )

    @readonly.migration(from_version=1, to_version=2)
    def migrate_readonly(document: dict[str, object]) -> dict[str, object]:
        document["appearance"] = {"theme": document.pop("theme")}
        return document

    with pytest.raises(CorylReadOnlyResourceError):
        readonly.migrate()

    invalid = app.configs.add("invalid", "config/invalid.toml", version=2)
    invalid.save({"version": 1, "theme": "light"})

    @invalid.migration(from_version=1, to_version=2)
    def migrate_invalid(document: dict[str, object]) -> list[str]:
        document["appearance"] = {"theme": document.pop("theme")}
        return ["not", "a", "mapping"]

    with pytest.raises(CorylValidationError, match="must return a mapping"):
        invalid.migrate()
