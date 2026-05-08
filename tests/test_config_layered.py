from __future__ import annotations

from textwrap import dedent

import pytest

from coryl import Coryl, CorylValidationError


def _write_text(path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dedent(content).strip() + "\n", encoding="utf-8")


def test_layered_config_merges_files_secrets_environment_and_runtime_in_order(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config_dir = tmp_path / "config"
    _write_text(
        config_dir / "defaults.toml",
        """
        debug = false

        [database]
        host = "defaults-host"
        port = 5432
        pool = 5
        """,
    )
    _write_text(
        config_dir / "local.toml",
        """
        [database]
        host = "local-host"
        """,
    )
    _write_text(
        config_dir / "production.toml",
        """
        [database]
        host = "production-host"
        port = 6432
        """,
    )
    _write_text(
        config_dir / ".secrets.toml",
        """
        [database]
        host = "secret-host"
        password = "top-secret"
        """,
    )

    app = Coryl(tmp_path)
    settings = app.configs.layered(
        "settings",
        files=[
            "config/defaults.toml",
            "config/local.toml",
            "config/production.toml",
        ],
        env_prefix="MYAPP",
        secrets="config/.secrets.toml",
    )

    monkeypatch.setenv("MYAPP_DATABASE__HOST", "env-host")
    monkeypatch.setenv("MYAPP_DATABASE__PORT", "6543")
    monkeypatch.setenv("OTHERAPP_DATABASE__HOST", "ignored")

    settings.override({"database.host": "runtime-host"})

    assert settings.load() == {
        "debug": False,
        "database": {
            "host": "runtime-host",
            "port": 6543,
            "pool": 5,
            "password": "top-secret",
        },
    }


def test_layered_config_deep_merges_dicts_and_replaces_lists_and_scalars(
    tmp_path,
) -> None:
    config_dir = tmp_path / "config"
    _write_text(
        config_dir / "defaults.toml",
        """
        mode = "defaults"
        features = ["a", "b"]

        [database.options]
        pool = 5
        ssl = true
        """,
    )
    _write_text(
        config_dir / "local.toml",
        """
        mode = "local"
        features = ["c"]

        [database.options]
        ssl = false
        timeout = 30
        """,
    )
    _write_text(
        config_dir / "production.toml",
        """
        mode = "production"
        """,
    )

    app = Coryl(tmp_path)
    settings = app.configs.layered(
        "settings",
        files=[
            "config/defaults.toml",
            "config/local.toml",
            "config/production.toml",
        ],
    )

    assert settings.as_dict() == {
        "mode": "production",
        "features": ["c"],
        "database": {"options": {"pool": 5, "ssl": False, "timeout": 30}},
    }


def test_layered_config_load_base_reload_and_secrets_dir_behavior(tmp_path) -> None:
    config_dir = tmp_path / "config"
    _write_text(
        config_dir / "defaults.toml",
        """
        debug = false
        token = "defaults-token"
        """,
    )
    local_path = config_dir / "local.toml"
    _write_text(
        local_path,
        """
        debug = true
        token = "local-token"
        """,
    )

    secrets_dir = tmp_path / "run" / "secrets"
    secrets_dir.mkdir(parents=True, exist_ok=True)
    (secrets_dir / "token").write_text("secret-token", encoding="utf-8")
    (secrets_dir / "region").write_text("eu-west-1", encoding="utf-8")

    app = Coryl(tmp_path)
    settings = app.configs.layered(
        "settings",
        files=["config/defaults.toml", "config/local.toml"],
        secrets_dir=secrets_dir,
    )

    assert settings.load_base() == {"debug": True, "token": "local-token"}
    assert settings.as_dict() == {
        "debug": True,
        "token": "secret-token",
        "region": "eu-west-1",
    }

    _write_text(
        local_path,
        """
        debug = false
        token = "local-token-updated"
        """,
    )

    assert settings.reload() == {
        "debug": False,
        "token": "secret-token",
        "region": "eu-west-1",
    }


def test_layered_config_required_missing_sources_are_explicit(tmp_path) -> None:
    config_dir = tmp_path / "config"
    _write_text(
        config_dir / "defaults.toml",
        """
        debug = false
        """,
    )

    app = Coryl(tmp_path)
    optional_settings = app.configs.layered(
        "optional_settings",
        files=["config/defaults.toml", "config/local.toml"],
        create=False,
        required=False,
    )
    required_settings = app.configs.layered(
        "required_settings",
        files=["config/defaults.toml", "config/local.toml"],
        create=False,
        required=True,
    )

    assert optional_settings.as_dict() == {"debug": False}

    with pytest.raises(FileNotFoundError, match=r"local\.toml"):
        required_settings.load()


def test_layered_config_environment_overrides_parse_conservatively_and_filter_prefix(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config_dir = tmp_path / "config"
    _write_text(
        config_dir / "defaults.toml",
        """
        [database]
        host = "file-host"
        """,
    )

    app = Coryl(tmp_path)
    settings = app.configs.layered(
        "settings",
        files=["config/defaults.toml"],
        env_prefix="MYAPP",
    )

    monkeypatch.setenv("MYAPP_DATABASE__HOST", "localhost")
    monkeypatch.setenv("MYAPP_DEBUG", "true")
    monkeypatch.setenv("MYAPP_DATABASE__PORT", "5432")
    monkeypatch.setenv("MYAPP_SERVICE__TIMEOUT", "1.5")
    monkeypatch.setenv("MYAPP_FEATURES", "[1, 2, 3]")
    monkeypatch.setenv("MYAPP_METADATA", '{"region": "eu"}')
    monkeypatch.setenv("MYAPP_BROKEN_JSON", "[1,")
    monkeypatch.setenv("MYAPP_RAW_VALUE", "abc:def")
    monkeypatch.setenv("OTHERAPP_DEBUG", "false")

    settings.override({"database.host": "runtime-host"})
    loaded = settings.as_dict()

    assert loaded["database"]["host"] == "runtime-host"
    assert loaded["database"]["port"] == 5432
    assert loaded["debug"] is True
    assert loaded["service"]["timeout"] == 1.5
    assert loaded["features"] == [1, 2, 3]
    assert loaded["metadata"] == {"region": "eu"}
    assert loaded["broken_json"] == "[1,"
    assert loaded["raw_value"] == "abc:def"
    assert "otherapp" not in loaded


def test_layered_config_runtime_override_helpers_support_dot_paths_and_validate_syntax(
    tmp_path,
) -> None:
    config_dir = tmp_path / "config"
    _write_text(
        config_dir / "defaults.toml",
        """
        debug = false

        [database]
        host = "file-host"
        """,
    )

    app = Coryl(tmp_path)
    settings = app.configs.layered("settings", files=["config/defaults.toml"])

    settings.override({"database.host": "override-host"})
    settings.apply_overrides(["debug=true", "database.port=6432", 'labels=["a", "b"]'])

    assert settings.as_dict() == {
        "debug": True,
        "database": {"host": "override-host", "port": 6432},
        "labels": ["a", "b"],
    }

    with pytest.raises(CorylValidationError, match="KEY=VALUE"):
        settings.apply_overrides(["debug"])
