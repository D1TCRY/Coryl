from __future__ import annotations

import pytest

from coryl import ConfigResource, Coryl, CorylValidationError


def test_basic_config_resource_supports_registration_round_trip_and_dot_paths(
    tmp_path,
) -> None:
    app = Coryl(tmp_path)

    settings = app.configs.add("settings", "config/settings.toml")
    profile = app.register_config("profile", "config/profile.toml")

    assert isinstance(settings, ConfigResource)
    assert isinstance(profile, ConfigResource)
    assert app.configs.get("settings") is settings
    assert app.configs.get("profile") is profile

    settings.save(
        {
            "debug": False,
            "database": {
                "host": "localhost",
                "ports": [5432, 5433],
            },
        }
    )
    profile.save({"name": "Coryl"})

    assert settings.load() == {
        "debug": False,
        "database": {"host": "localhost", "ports": [5432, 5433]},
    }
    assert profile.load() == {"name": "Coryl"}
    assert settings.get("database.host") == "localhost"
    assert settings.get("database.ports.1") == 5433
    assert settings.get("database.user") is None
    assert settings.get("database.user", "postgres") == "postgres"
    assert settings.require("database.host") == "localhost"

    updated = settings.update({"debug": True}, timezone="Europe/Rome")

    assert updated == {
        "debug": True,
        "database": {"host": "localhost", "ports": [5432, 5433]},
        "timezone": "Europe/Rome",
    }
    assert settings.load() == updated

    with pytest.raises(CorylValidationError, match="database.user"):
        settings.require("database.user")


def test_basic_config_resource_handles_non_mapping_documents_where_supported(
    tmp_path,
) -> None:
    app = Coryl(tmp_path)
    entries = app.configs.add("entries", "config/entries.json")

    entries.save([{"name": "Ada"}, {"name": "Grace"}])

    assert entries.load() == [{"name": "Ada"}, {"name": "Grace"}]
    assert entries.get("0.name") == "Ada"
    assert entries.get("1.name") == "Grace"
    assert entries.get("2.name") is None

    with pytest.raises(CorylValidationError, match="2.name"):
        entries.require("2.name")

    with pytest.raises(TypeError, match="mapping-based document"):
        entries.update(active=True)
