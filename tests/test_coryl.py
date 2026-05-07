from __future__ import annotations

import importlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

import coryl.resources as coryl_resources

from coryl import (
    AssetGroup,
    CacheResource,
    ConfigResource,
    Coryl,
    CorylInvalidResourceKindError,
    CorylLockTimeoutError,
    CorylOptionalDependencyError,
    CorylPathError,
    CorylReadOnlyResourceError,
    CorylUnsupportedFormatError,
    CorylUnsafePathError,
    CorylValidationError,
    LayeredConfigResource,
    MANIFEST_VERSION,
    ManifestFormatError,
    PackageAssetGroup,
    PackageAssetResource,
    ResourceKindError,
    ResourceNotRegisteredError,
    ResourceSpec,
)


class CorylTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.outside_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.outside_root = Path(self.outside_dir.name)
        self._directory_links: list[Path] = []

    def tearDown(self) -> None:
        for link_path in reversed(self._directory_links):
            self._remove_directory_link(link_path)
        self.outside_dir.cleanup()
        self.temp_dir.cleanup()

    def test_registers_files_and_directories(self) -> None:
        manager = Coryl(
            self.root,
            resources={
                "config": ResourceSpec.file("config/settings.json"),
                "assets": ResourceSpec.directory("assets"),
            },
        )

        self.assertTrue(manager.path("config").is_file())
        self.assertTrue(manager.path("assets").is_dir())
        self.assertEqual(manager.root_folder_path, self.root.resolve())
        self.assertEqual(manager.config_file_path, manager.path("config"))

    def test_registration_methods_keep_paths_inside_root(self) -> None:
        manager = Coryl(self.root)

        resources = {
            "notes": manager.register_file("notes", "data/notes.txt"),
            "exports": manager.register_directory("exports", "build/exports"),
            "settings": manager.register_config("settings", "config/settings.toml"),
            "cache": manager.register_cache("cache", ".cache/http"),
            "assets": manager.register_assets("assets", "assets/ui"),
            "logs": manager.register("logs", ResourceSpec.file("runtime/logs.json")),
        }

        self.assertIsInstance(resources["settings"], ConfigResource)
        self.assertIsInstance(resources["cache"], CacheResource)
        self.assertIsInstance(resources["assets"], AssetGroup)

        for name, resource in resources.items():
            with self.subTest(resource=name):
                self.assertTrue(resource.path.is_relative_to(manager.root_path))

    def test_single_root_mode_exposes_data_and_logs_namespaces(self) -> None:
        manager = Coryl(self.root)

        state = manager.data.add("state", "runtime/state.json")
        logs = manager.logs.add("main", "runtime/logs")

        self.assertEqual(state.path, (self.root / "runtime" / "state.json").resolve())
        self.assertEqual(logs.path, (self.root / "runtime" / "logs").resolve())
        self.assertEqual(manager.data.get("state").role, "data")
        self.assertEqual(manager.logs.get("main").role, "logs")

    def test_for_app_requires_optional_platformdirs_extra(self) -> None:
        with mock.patch(
            "coryl.manager.import_module",
            side_effect=ModuleNotFoundError("No module named 'platformdirs'"),
        ):
            with self.assertRaises(CorylOptionalDependencyError) as caught:
                Coryl.for_app("mytool")

        self.assertIn("pip install coryl[platform]", str(caught.exception))

    def test_for_app_routes_namespaces_to_platformdirs_roots(self) -> None:
        platform_roots = {
            "config": self.root / "platform-config",
            "cache": self.root / "platform-cache",
            "data": self.root / "platform-data",
            "log": self.root / "platform-log",
        }
        fake_platformdirs, calls = self._make_fake_platformdirs_module(platform_roots)

        with mock.patch("coryl.manager.import_module", return_value=fake_platformdirs):
            app = Coryl.for_app(
                "mytool",
                app_author="Acme",
                version="1.2.3",
                roaming=True,
                multipath=True,
                ensure=True,
            )

        self.assertEqual(
            calls,
            [
                {
                    "appname": "mytool",
                    "appauthor": "Acme",
                    "version": "1.2.3",
                    "roaming": True,
                    "multipath": True,
                    "ensure_exists": True,
                }
            ],
        )
        self.assertEqual(app.root_path, platform_roots["data"].resolve())
        self.assertEqual(app.config_root_path, platform_roots["config"].resolve())
        self.assertEqual(app.cache_root_path, platform_roots["cache"].resolve())
        self.assertEqual(app.data_root_path, platform_roots["data"].resolve())
        self.assertEqual(app.log_root_path, platform_roots["log"].resolve())
        self.assertTrue(app.config_root_path.is_dir())
        self.assertTrue(app.cache_root_path.is_dir())
        self.assertTrue(app.data_root_path.is_dir())
        self.assertTrue(app.log_root_path.is_dir())

        settings = app.configs.add("settings", "settings.toml")
        cache = app.caches.add("http", "http")
        data = app.data.add("state", "state.json")
        log = app.logs.add("main", "app.log")

        self.assertEqual(settings.path, (platform_roots["config"] / "settings.toml").resolve())
        self.assertEqual(cache.path, (platform_roots["cache"] / "http").resolve())
        self.assertEqual(data.path, (platform_roots["data"] / "state.json").resolve())
        self.assertEqual(log.path, (platform_roots["log"] / "app.log").resolve())
        self.assertEqual(app.path("settings"), settings.path)
        self.assertEqual(app.path("http"), cache.path)
        self.assertEqual(app.path("state"), data.path)
        self.assertEqual(app.path("main"), log.path)

        audit = app.audit_paths()
        self.assertTrue(audit["resources"]["settings"]["safe"])
        self.assertTrue(audit["resources"]["http"]["safe"])
        self.assertTrue(audit["resources"]["state"]["safe"])
        self.assertTrue(audit["resources"]["main"]["safe"])

    def test_registration_methods_reject_traversal(self) -> None:
        manager = Coryl(self.root)
        cases = {
            "register_file": lambda: manager.register_file("notes", "data/../notes.txt"),
            "register_directory": lambda: manager.register_directory(
                "exports", "build/../exports"
            ),
            "register_config": lambda: manager.register_config(
                "settings", "config/../settings.toml"
            ),
            "register_cache": lambda: manager.register_cache("cache", ".cache/../http"),
            "register_assets": lambda: manager.register_assets("assets", "assets/../ui"),
            "resource_spec": lambda: manager.register(
                "logs",
                ResourceSpec.file("runtime/../logs.json"),
            ),
        }

        for label, action in cases.items():
            with self.subTest(method=label):
                with self.assertRaises(CorylUnsafePathError):
                    action()

    def test_manager_rejects_absolute_paths_by_default(self) -> None:
        manager = Coryl(self.root)

        with self.assertRaises(CorylPathError):
            manager.register_file("absolute", self.root / "data" / "absolute.txt")

    def test_rejects_directory_links_that_escape_the_root(self) -> None:
        manager = Coryl(self.root)
        link_path = self.root / "linked-assets"
        self._make_directory_link(link_path, self.outside_root)

        with self.assertRaises(CorylUnsafePathError):
            manager.register_directory("linked", "linked-assets")

    def test_json_round_trip_and_legacy_aliases(self) -> None:
        manager = Coryl(self.root)
        manager.register_file("data", "storage/data.json")

        manager.write_content("data", {"name": "Coryl", "version": 1})

        self.assertEqual(manager.content("data"), {"name": "Coryl", "version": 1})
        self.assertEqual(manager.data_file_path.name, "data.json")
        with self.assertRaises(AttributeError):
            _ = manager.data_directory_path

    def test_write_text_uses_atomic_replacement_by_default(self) -> None:
        manager = Coryl(self.root)
        report = manager.register_file("report", "reports/daily.txt")

        report.write_text("daily summary")

        self.assertEqual(report.read_text(), "daily summary")
        self.assertEqual(self._temporary_files_for(report.path), [])

    def test_write_bytes_uses_atomic_replacement_by_default(self) -> None:
        manager = Coryl(self.root)
        archive = manager.register_file("archive", "data/archive.bin")

        archive.write_bytes(b"\x00\x01\x02")

        self.assertEqual(archive.read_bytes(), b"\x00\x01\x02")
        self.assertEqual(self._temporary_files_for(archive.path), [])

    def test_lock_context_manager_creates_and_uses_lock_file(self) -> None:
        manager = Coryl(self.root)
        settings = manager.register_file("settings", "config/settings.json")
        file_lock_class, timeout_error = self._make_fake_lock_backend()
        expected_lock_path = settings.path.parent / f"{settings.path.name}.lock"

        with mock.patch(
            "coryl._locks._load_filelock_backend",
            return_value=(file_lock_class, timeout_error),
        ):
            with settings.lock() as locked_resource:
                self.assertIs(locked_resource, settings)
                self.assertEqual(file_lock_class.created_paths, [expected_lock_path])
                self.assertEqual(file_lock_class.requested_timeouts, [None])
                self.assertTrue(expected_lock_path.exists())

    def test_lock_dependency_missing_error_is_clear(self) -> None:
        manager = Coryl(self.root)
        settings = manager.register_file("settings", "config/settings.json")

        with mock.patch(
            "coryl._locks.import_module",
            side_effect=ModuleNotFoundError("No module named 'filelock'"),
        ):
            with self.assertRaises(CorylOptionalDependencyError) as caught:
                with settings.lock():
                    pass

        self.assertIn("pip install coryl[lock]", str(caught.exception))

    def test_explicit_structured_write_helpers_still_work(self) -> None:
        manager = Coryl(self.root)
        payload = {"name": "Coryl", "version": 1}

        json_resource = manager.register_file("json", "storage/data.json")
        toml_resource = manager.register_file("toml", "storage/data.toml")
        yaml_resource = manager.register_file("yaml", "storage/data.yaml")

        json_resource.write_json(payload)
        toml_resource.write_toml(payload)
        yaml_resource.write_yaml(payload)

        self.assertEqual(json_resource.read_json(), payload)
        self.assertEqual(toml_resource.read_toml(), payload)
        self.assertEqual(yaml_resource.read_yaml(), payload)

    def test_config_save_still_uses_safe_structured_writes(self) -> None:
        manager = Coryl(self.root)
        settings = manager.configs.add("settings", "config/settings.yaml")

        settings.save({"theme": "dark", "language": "en"})

        self.assertEqual(settings.load(), {"theme": "dark", "language": "en"})
        self.assertEqual(self._temporary_files_for(settings.path), [])

    def test_toml_config_round_trip(self) -> None:
        manager = Coryl(self.root)
        settings = manager.configs.add("settings", "config/settings.toml")

        settings.save(
            {
                "app_name": "Coryl",
                "debug": True,
                "ports": [8000, 8001],
                "database": {"host": "localhost", "port": 5432},
            }
        )

        self.assertIsInstance(settings, ConfigResource)
        self.assertEqual(
            settings.load(),
            {
                "app_name": "Coryl",
                "debug": True,
                "ports": [8000, 8001],
                "database": {"host": "localhost", "port": 5432},
            },
        )
        self.assertEqual(manager.content("settings")["database"]["port"], 5432)

    def test_yaml_config_round_trip_and_update(self) -> None:
        manager = Coryl(self.root)
        settings = manager.configs.add("settings", "config/settings.yaml")

        settings.save({"theme": "light", "language": "en"})
        merged = settings.update(language="it", timezone="Europe/Rome")

        self.assertEqual(
            merged,
            {"theme": "light", "language": "it", "timezone": "Europe/Rome"},
        )
        self.assertEqual(settings.load()["timezone"], "Europe/Rome")

    def test_config_load_typed_validates_data(self) -> None:
        manager = Coryl(self.root)
        settings = manager.configs.add("settings", "config/settings.json")
        fake_pydantic = self._make_fake_pydantic_module()
        settings.save({"host": "localhost", "port": 5432, "debug": True})

        with mock.patch("coryl.resources.import_module", return_value=fake_pydantic):
            loaded = settings.load_typed(fake_pydantic.SettingsModel)

        self.assertIsInstance(loaded, fake_pydantic.SettingsModel)
        self.assertEqual(loaded.host, "localhost")
        self.assertEqual(loaded.port, 5432)
        self.assertTrue(loaded.debug)

    def test_config_load_typed_uses_registered_schema_when_available(self) -> None:
        manager = Coryl(self.root)
        fake_pydantic = self._make_fake_pydantic_module()
        settings = manager.configs.add(
            "settings",
            "config/settings.toml",
            schema=fake_pydantic.SettingsModel,
        )
        settings.save({"host": "localhost", "port": 5432, "debug": False})

        with mock.patch("coryl.resources.import_module", return_value=fake_pydantic):
            loaded = settings.load_typed()

        self.assertIsInstance(loaded, fake_pydantic.SettingsModel)
        self.assertFalse(loaded.debug)

    def test_config_load_typed_invalid_data_raises_validation_error(self) -> None:
        manager = Coryl(self.root)
        settings = manager.configs.add("settings", "config/settings.yaml")
        fake_pydantic = self._make_fake_pydantic_module()
        settings.save({"host": "localhost", "port": "not-an-int"})

        with mock.patch("coryl.resources.import_module", return_value=fake_pydantic):
            with self.assertRaises(CorylValidationError) as caught:
                settings.load_typed(fake_pydantic.SettingsModel)

        self.assertIn("Configuration validation failed", str(caught.exception))
        self.assertIn("settings", str(caught.exception))

    def test_config_save_typed_writes_expected_data(self) -> None:
        manager = Coryl(self.root)
        settings = manager.configs.add("settings", "config/settings.yaml")
        fake_pydantic = self._make_fake_pydantic_module()
        instance = fake_pydantic.SettingsModel("localhost", 5432, True)

        with mock.patch("coryl.resources.import_module", return_value=fake_pydantic):
            settings.save_typed(instance)

        self.assertEqual(
            settings.load(),
            {"host": "localhost", "port": 5432, "debug": True},
        )

    def test_typed_config_helpers_require_optional_pydantic_extra(self) -> None:
        manager = Coryl(self.root)
        settings = manager.configs.add("settings", "config/settings.json")
        settings.save({"host": "localhost", "port": 5432})
        fake_pydantic = self._make_fake_pydantic_module()

        with mock.patch(
            "coryl.resources.import_module",
            side_effect=ModuleNotFoundError("No module named 'pydantic'"),
        ):
            with self.assertRaises(CorylOptionalDependencyError) as caught:
                settings.load_typed(fake_pydantic.SettingsModel)

        self.assertIn("pip install coryl[pydantic]", str(caught.exception))

    def test_config_require_supports_dot_paths(self) -> None:
        manager = Coryl(self.root)
        settings = manager.configs.add("settings", "config/settings.json")
        settings.save(
            {
                "database": {
                    "host": "localhost",
                    "ports": [5432, 5433],
                }
            }
        )

        self.assertEqual(settings.require("database.host"), "localhost")
        self.assertEqual(settings.require("database.ports.1"), 5433)
        self.assertEqual(settings.require("database.user", "postgres"), "postgres")

        with self.assertRaises(CorylValidationError) as caught:
            settings.require("database.user")

        self.assertIn("database.user", str(caught.exception))

    def test_config_migrate_applies_v1_to_v2_migration(self) -> None:
        manager = Coryl(self.root)
        settings = manager.configs.add("settings", "config/settings.toml", version=2)
        settings.save({"version": 1, "theme": "light"})

        @settings.migration(from_version=1, to_version=2)
        def migrate_v1_to_v2(data: dict[str, object]) -> dict[str, object]:
            theme = data.pop("theme")
            data["appearance"] = {"theme": theme}
            return data

        migrated = settings.migrate()

        self.assertEqual(
            migrated,
            {"version": 2, "appearance": {"theme": "light"}},
        )
        self.assertEqual(settings.load(), migrated)

    def test_config_migrate_applies_multiple_sequential_migrations(self) -> None:
        manager = Coryl(self.root)
        settings = manager.configs.add("settings", "config/settings.toml", version=3)
        settings.save({"version": 1, "theme": "light"})

        @settings.migration(from_version=1, to_version=2)
        def migrate_v1_to_v2(data: dict[str, object]) -> dict[str, object]:
            data["appearance"] = {"theme": data.pop("theme")}
            return data

        @settings.migration(from_version=2, to_version=3)
        def migrate_v2_to_v3(data: dict[str, object]) -> dict[str, object]:
            appearance = data.setdefault("appearance", {})
            if not isinstance(appearance, dict):
                raise AssertionError("appearance should be a dict during the migration test.")
            appearance["mode"] = "system"
            return data

        migrated = settings.migrate()

        self.assertEqual(
            migrated,
            {"version": 3, "appearance": {"theme": "light", "mode": "system"}},
        )

    def test_config_migrate_missing_path_raises_clear_error(self) -> None:
        manager = Coryl(self.root)
        settings = manager.configs.add("settings", "config/settings.toml", version=3)
        settings.save({"version": 1, "theme": "light"})

        @settings.migration(from_version=1, to_version=2)
        def migrate_v1_to_v2(data: dict[str, object]) -> dict[str, object]:
            data["appearance"] = {"theme": data.pop("theme")}
            return data

        with self.assertRaises(CorylValidationError) as caught:
            settings.migrate()

        self.assertIn("No migration registered", str(caught.exception))
        self.assertIn("target version 3", str(caught.exception))

    def test_config_migrate_when_already_current_does_not_save(self) -> None:
        manager = Coryl(self.root)
        settings = manager.configs.add("settings", "config/settings.toml", version=2)
        settings.save({"version": 2, "theme": "light"})

        with mock.patch(
            "coryl.resources._atomic_write_text",
            wraps=coryl_resources._atomic_write_text,
        ) as atomic_write:
            migrated = settings.migrate()

        atomic_write.assert_not_called()
        self.assertEqual(migrated, {"version": 2, "theme": "light"})
        self.assertEqual(settings.load(), {"version": 2, "theme": "light"})

    def test_config_migrate_saves_migrated_file_atomically(self) -> None:
        manager = Coryl(self.root)
        settings = manager.configs.add("settings", "config/settings.yaml", version=2)
        settings.save({"version": 1, "theme": "light"})

        @settings.migration(from_version=1, to_version=2)
        def migrate_v1_to_v2(data: dict[str, object]) -> dict[str, object]:
            data["appearance"] = {"theme": data.pop("theme")}
            return data

        with mock.patch(
            "coryl.resources._atomic_write_text",
            wraps=coryl_resources._atomic_write_text,
        ) as atomic_write:
            migrated = settings.migrate()

        atomic_write.assert_called_once()
        self.assertEqual(
            migrated,
            {"version": 2, "appearance": {"theme": "light"}},
        )
        self.assertEqual(self._temporary_files_for(settings.path), [])

    def test_layered_config_uses_secrets_dir_as_final_override(self) -> None:
        settings_path = self.root / "config" / "settings.yaml"
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        settings_path.write_text(
            """
theme: light
token: base-token
""".strip(),
            encoding="utf-8",
        )

        secrets_dir = self.outside_root / "run" / "secrets"
        secrets_dir.mkdir(parents=True, exist_ok=True)
        (secrets_dir / "token").write_text("secret-token", encoding="utf-8")
        (secrets_dir / "region").write_text("eu-west-1", encoding="utf-8")

        manager = Coryl(self.root)
        settings = manager.configs.layered(
            "settings",
            "config/settings.yaml",
            secrets_dir=secrets_dir,
        )

        self.assertIsInstance(settings, LayeredConfigResource)
        self.assertEqual(settings.load_base(), {"theme": "light", "token": "base-token"})
        self.assertEqual(
            settings.load(),
            {"theme": "light", "token": "secret-token", "region": "eu-west-1"},
        )

    def test_layered_config_applies_explicit_merge_order(self) -> None:
        config_dir = self.root / "config"
        config_dir.mkdir(parents=True, exist_ok=True)
        (config_dir / "defaults.toml").write_text(
            """
debug = false

[database]
host = "defaults-host"
port = 5432
""".strip(),
            encoding="utf-8",
        )
        (config_dir / "local.toml").write_text(
            """
[database]
host = "local-host"
""".strip(),
            encoding="utf-8",
        )
        (config_dir / "production.toml").write_text(
            """
[database]
host = "production-host"
port = 6432
""".strip(),
            encoding="utf-8",
        )
        (config_dir / ".secrets.toml").write_text(
            """
[database]
host = "secret-host"
password = "top-secret"
""".strip(),
            encoding="utf-8",
        )

        manager = Coryl(self.root)
        settings = manager.configs.layered(
            "settings",
            files=[
                "config/defaults.toml",
                "config/local.toml",
                "config/production.toml",
            ],
            env_prefix="MYAPP",
            secrets="config/.secrets.toml",
        )

        with mock.patch.dict(os.environ, {"MYAPP_DATABASE__HOST": "env-host"}, clear=False):
            settings.override({"database.host": "runtime-host"})
            loaded = settings.as_dict()

        self.assertEqual(loaded["database"]["host"], "runtime-host")
        self.assertEqual(loaded["database"]["port"], 6432)
        self.assertEqual(loaded["database"]["password"], "top-secret")
        self.assertFalse(loaded["debug"])

    def test_layered_config_deep_merges_dicts_and_replaces_lists(self) -> None:
        config_dir = self.root / "config"
        config_dir.mkdir(parents=True, exist_ok=True)
        (config_dir / "defaults.toml").write_text(
            """
features = ["a", "b"]

[database]
host = "localhost"

[database.options]
pool = 5
ssl = true
""".strip(),
            encoding="utf-8",
        )
        (config_dir / "local.toml").write_text(
            """
features = ["c"]

[database.options]
ssl = false
timeout = 30
""".strip(),
            encoding="utf-8",
        )

        manager = Coryl(self.root)
        settings = manager.configs.layered(
            "settings",
            files=["config/defaults.toml", "config/local.toml"],
        )

        loaded = settings.as_dict()

        self.assertEqual(loaded["features"], ["c"])
        self.assertEqual(
            loaded["database"]["options"],
            {"pool": 5, "ssl": False, "timeout": 30},
        )

    def test_layered_config_environment_overrides_parse_conservatively(self) -> None:
        config_dir = self.root / "config"
        config_dir.mkdir(parents=True, exist_ok=True)
        (config_dir / "defaults.toml").write_text(
            """
debug = false

[database]
port = 5000
""".strip(),
            encoding="utf-8",
        )

        manager = Coryl(self.root)
        settings = manager.configs.layered(
            "settings",
            files=["config/defaults.toml"],
            env_prefix="MYAPP",
        )

        with mock.patch.dict(
            os.environ,
            {
                "MYAPP_DEBUG": "true",
                "MYAPP_DATABASE__PORT": "6543",
                "MYAPP_SERVICE__TIMEOUT": "1.5",
                "MYAPP_FEATURES": "[1, 2, 3]",
                "MYAPP_METADATA": '{"region": "eu"}',
                "MYAPP_HOST": "localhost",
            },
            clear=False,
        ):
            loaded = settings.as_dict()

        self.assertTrue(loaded["debug"])
        self.assertEqual(loaded["database"]["port"], 6543)
        self.assertEqual(loaded["service"]["timeout"], 1.5)
        self.assertEqual(loaded["features"], [1, 2, 3])
        self.assertEqual(loaded["metadata"], {"region": "eu"})
        self.assertEqual(loaded["host"], "localhost")

    def test_layered_config_secrets_file_overrides_regular_files(self) -> None:
        config_dir = self.root / "config"
        config_dir.mkdir(parents=True, exist_ok=True)
        (config_dir / "defaults.toml").write_text(
            """
token = "base-token"
""".strip(),
            encoding="utf-8",
        )
        (config_dir / ".secrets.toml").write_text(
            """
token = "secret-token"
""".strip(),
            encoding="utf-8",
        )

        manager = Coryl(self.root)
        settings = manager.configs.layered(
            "settings",
            files=["config/defaults.toml"],
            secrets="config/.secrets.toml",
        )

        self.assertEqual(settings.as_dict()["token"], "secret-token")

    def test_layered_config_runtime_override_helpers_and_reload(self) -> None:
        config_dir = self.root / "config"
        config_dir.mkdir(parents=True, exist_ok=True)
        defaults_path = config_dir / "defaults.toml"
        defaults_path.write_text(
            """
debug = false

[database]
host = "file-host"
""".strip(),
            encoding="utf-8",
        )

        manager = Coryl(self.root)
        settings = manager.configs.layered(
            "settings",
            files=["config/defaults.toml"],
        )

        settings.override({"database.host": "override-host"})
        settings.apply_overrides(["debug=true", "database.port=6432"])

        defaults_path.write_text(
            """
debug = false

[database]
host = "file-host-updated"
name = "primary"
""".strip(),
            encoding="utf-8",
        )

        reloaded = settings.reload()

        self.assertEqual(reloaded["database"]["host"], "override-host")
        self.assertEqual(reloaded["database"]["port"], 6432)
        self.assertEqual(reloaded["database"]["name"], "primary")
        self.assertTrue(reloaded["debug"])

    def test_layered_config_required_files_are_enforced_when_requested(self) -> None:
        config_dir = self.root / "config"
        config_dir.mkdir(parents=True, exist_ok=True)
        (config_dir / "defaults.toml").write_text(
            """
debug = false
""".strip(),
            encoding="utf-8",
        )

        manager = Coryl(self.root)
        optional_settings = manager.configs.layered(
            "optional_settings",
            files=["config/defaults.toml", "config/local.toml"],
            create=False,
            required=False,
        )
        required_settings = manager.configs.layered(
            "required_settings",
            files=["config/defaults.toml", "config/local.toml"],
            create=False,
            required=True,
        )

        self.assertEqual(optional_settings.as_dict()["debug"], False)
        with self.assertRaises(FileNotFoundError):
            required_settings.load()

    def test_layered_config_get_require_and_as_dict_support_dot_paths(self) -> None:
        config_dir = self.root / "config"
        config_dir.mkdir(parents=True, exist_ok=True)
        (config_dir / "defaults.toml").write_text(
            """
[database]
host = "localhost"
ports = [5432, 5433]
""".strip(),
            encoding="utf-8",
        )

        manager = Coryl(self.root)
        settings = manager.configs.layered(
            "settings",
            files=["config/defaults.toml"],
        )

        self.assertEqual(settings.get("database.host"), "localhost")
        self.assertEqual(settings.get("database.user"), None)
        self.assertEqual(settings.require("database.ports.1"), 5433)
        self.assertEqual(settings.as_dict()["database"]["host"], "localhost")

        with self.assertRaises(CorylValidationError):
            settings.require("database.user")

    def test_readonly_config_cannot_save_or_update(self) -> None:
        settings_path = self.root / "config" / "settings.yaml"
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        settings_path.write_text("theme: light\n", encoding="utf-8")

        manager = Coryl(self.root)
        settings = manager.register_config("settings", "config/settings.yaml", readonly=True)

        self.assertEqual(settings.load(), {"theme": "light"})

        with self.assertRaises(CorylReadOnlyResourceError):
            settings.save({"theme": "dark"})

        with self.assertRaises(CorylReadOnlyResourceError):
            settings.update(theme="dark")

    def test_config_update_with_lock_true_works(self) -> None:
        manager = Coryl(self.root)
        settings = manager.configs.add("settings", "config/settings.yaml")
        file_lock_class, timeout_error = self._make_fake_lock_backend()
        settings.save({"theme": "light", "language": "en"})

        with mock.patch(
            "coryl._locks._load_filelock_backend",
            return_value=(file_lock_class, timeout_error),
        ):
            merged = settings.update(language="it", lock=True)

        self.assertEqual(merged, {"theme": "light", "language": "it"})
        self.assertEqual(settings.load(), {"theme": "light", "language": "it"})
        self.assertEqual(file_lock_class.requested_timeouts, [None])

    def test_lock_timeout_maps_to_coryl_lock_timeout_error(self) -> None:
        manager = Coryl(self.root)
        settings = manager.register_file("settings", "config/settings.json")
        file_lock_class, timeout_error = self._make_timeout_lock_backend()

        with mock.patch(
            "coryl._locks._load_filelock_backend",
            return_value=(file_lock_class, timeout_error),
        ):
            with self.assertRaises(CorylLockTimeoutError) as caught:
                with settings.lock(timeout=0.01):
                    pass

        self.assertIn(".lock", str(caught.exception))

    def test_atomic_writes_recreate_missing_parent_directories(self) -> None:
        manager = Coryl(self.root)
        report = manager.register_file("report", "runtime/reports/daily.txt")

        shutil.rmtree(self.root / "runtime")
        report.write_text("restored")

        self.assertTrue(report.path.parent.is_dir())
        self.assertEqual(report.read_text(), "restored")

    def test_atomic_false_still_writes_text(self) -> None:
        manager = Coryl(self.root)
        report = manager.register_file("report", "reports/daily.txt")

        report.write_text("plain write", atomic=False)

        self.assertEqual(report.read_text(), "plain write")
        self.assertEqual(self._temporary_files_for(report.path), [])

    def test_atomic_write_cleans_up_temp_files_after_failure(self) -> None:
        manager = Coryl(self.root)
        report = manager.register_file("report", "reports/daily.txt")
        report.write_text("original")

        with mock.patch("coryl._io.os.replace", side_effect=OSError("replace failed")):
            with self.assertRaises(OSError):
                report.write_text("updated")

        self.assertEqual(report.read_text(), "original")
        self.assertEqual(self._temporary_files_for(report.path), [])

    def test_readonly_file_cannot_write(self) -> None:
        report_path = self.root / "reports" / "daily.txt"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text("original", encoding="utf-8")

        manager = Coryl(self.root)
        report = manager.register_file("report", "reports/daily.txt", readonly=True)

        self.assertTrue(report.readonly)
        self.assertEqual(report.read_text(), "original")

        with self.assertRaises(CorylReadOnlyResourceError) as caught:
            report.write_text("updated")

        self.assertIn("read-only", str(caught.exception))
        self.assertIn("written", str(caught.exception))

    def test_config_resources_must_use_structured_files(self) -> None:
        manager = Coryl(self.root)

        with self.assertRaises(CorylUnsupportedFormatError):
            manager.register_config("settings", "config/settings.txt")

    def test_cache_and_assets_must_be_directories(self) -> None:
        manager = Coryl(self.root)
        cases = {
            "cache": {"path": "runtime/cache.txt", "kind": "file", "role": "cache"},
            "assets": {"path": "assets/logo.svg", "kind": "file", "role": "assets"},
        }

        for name, definition in cases.items():
            with self.subTest(role=name):
                with self.assertRaises(CorylValidationError):
                    manager.register(name, definition)

    def test_legacy_manifest_schema_still_works(self) -> None:
        manifest_path = self.root / "app.json"
        manifest_path.write_text(
            json.dumps(
                {
                    "paths": {
                        "files": {"settings": "config/settings.json"},
                        "directories": {"cache": "runtime/cache"},
                    }
                }
            ),
            encoding="utf-8",
        )

        manager = Coryl(self.root, manifest_path="app.json")

        self.assertTrue(manager.file("settings").path.is_file())
        self.assertTrue(manager.directory("cache").path.is_dir())
        self.assertEqual(manager.file("settings").role, "resource")

    def test_manifest_loading_uses_the_same_safe_resolver(self) -> None:
        manifest_path = self.root / "app.yaml"
        manifest_path.write_text(
            """
resources:
  settings:
    path: config/../settings.yaml
    kind: file
    role: config
""".strip(),
            encoding="utf-8",
        )

        with self.assertRaises(CorylUnsafePathError):
            Coryl(self.root, manifest_path="app.yaml")

    def test_toml_manifest_with_specialized_roles(self) -> None:
        manifest_path = self.root / "app.toml"
        manifest_path.write_text(
            """
version = 2

[resources.settings]
path = "config/settings.toml"
kind = "file"
role = "config"
readonly = true
required = true
format = "toml"
schema = "app.settings.v1"

[resources.http_cache]
path = ".cache/http"
kind = "directory"
role = "cache"
backend = "diskcache"

[resources.assets]
path = "assets"
kind = "directory"
role = "assets"
""".strip(),
            encoding="utf-8",
        )

        manager = Coryl(self.root, manifest_path=manifest_path)

        self.assertIsInstance(manager.configs.get("settings"), ConfigResource)
        self.assertIsInstance(manager.caches.get("http_cache"), CacheResource)
        self.assertIsInstance(manager.assets.get("assets"), AssetGroup)
        self.assertEqual(manager.manifest["version"], MANIFEST_VERSION)
        self.assertTrue(manager.resource("settings").readonly)
        self.assertTrue(manager.resource("settings").required)
        self.assertEqual(manager.resource("settings").declared_format, "toml")
        self.assertEqual(manager.resource("settings").schema, "app.settings.v1")
        self.assertEqual(manager.resource("http_cache").backend, "diskcache")

    def test_modern_manifest_schema_can_be_reloaded(self) -> None:
        manifest_path = self.root / "app.yaml"
        manifest_path.write_text(
            """
version: 2
resources:
  settings:
    path: config/settings.yaml
    kind: file
    role: config
  assets:
    path: assets
    kind: directory
    role: assets
""".strip(),
            encoding="utf-8",
        )

        manager = Coryl(self.root, manifest_path=manifest_path)
        self.assertTrue(manager.settings_file_path.is_file())
        self.assertTrue(manager.assets_directory_path.is_dir())

        manifest_path.write_text(
            """
version: 2
resources:
  settings:
    path: config/new-settings.yaml
    kind: file
    role: config
""".strip(),
            encoding="utf-8",
        )

        manager.load_config()
        self.assertEqual(manager.settings_file_path.name, "new-settings.yaml")
        with self.assertRaises(AttributeError):
            _ = manager.assets_directory_path

    def test_manifest_rejects_unsupported_version(self) -> None:
        manifest_path = self.root / "app.yaml"
        manifest_path.write_text(
            """
version: 3
resources:
  settings:
    path: config/settings.yaml
    kind: file
""".strip(),
            encoding="utf-8",
        )

        with self.assertRaises(ManifestFormatError) as caught:
            Coryl(self.root, manifest_path="app.yaml")

        self.assertIn("supports version 2", str(caught.exception))

    def test_manifest_rejects_unknown_kind_with_clear_error(self) -> None:
        manifest_path = self.root / "app.yaml"
        manifest_path.write_text(
            """
version: 2
resources:
  socket:
    path: runtime/socket
    kind: socket
""".strip(),
            encoding="utf-8",
        )

        with self.assertRaises(CorylInvalidResourceKindError) as caught:
            Coryl(self.root, manifest_path="app.yaml")

        self.assertIn("Resource 'socket' is invalid", str(caught.exception))
        self.assertIn("either 'file' or 'directory'", str(caught.exception))

    def test_manifest_rejects_incompatible_role_and_kind_with_clear_error(self) -> None:
        manifest_path = self.root / "app.yaml"
        manifest_path.write_text(
            """
version: 2
resources:
  http_cache:
    path: .cache/http
    kind: file
    role: cache
""".strip(),
            encoding="utf-8",
        )

        with self.assertRaises(CorylValidationError) as caught:
            Coryl(self.root, manifest_path="app.yaml")

        self.assertIn("Resource 'http_cache' is invalid", str(caught.exception))
        self.assertIn("directories", str(caught.exception))

    def test_manifest_rejects_duplicate_names_in_json(self) -> None:
        manifest_path = self.root / "app.json"
        manifest_path.write_text(
            """
{
  "version": 2,
  "resources": {
    "settings": {
      "path": "config/settings.toml",
      "kind": "file"
    },
    "settings": {
      "path": "config/other-settings.toml",
      "kind": "file"
    }
  }
}
""".strip(),
            encoding="utf-8",
        )

        with self.assertRaises(ManifestFormatError) as caught:
            Coryl(self.root, manifest_path="app.json")

        self.assertIn("Duplicate key 'settings'", str(caught.exception))

    def test_legacy_manifest_rejects_duplicate_names_across_sections(self) -> None:
        manifest_path = self.root / "app.yaml"
        manifest_path.write_text(
            """
paths:
  files:
    shared: config/settings.toml
  directories:
    shared: runtime/cache
""".strip(),
            encoding="utf-8",
        )

        with self.assertRaises(ManifestFormatError) as caught:
            Coryl(self.root, manifest_path="app.yaml")

        self.assertIn("duplicate resource names", str(caught.exception))
        self.assertIn("'shared'", str(caught.exception))

    def test_manifest_readonly_resource_blocks_writes(self) -> None:
        settings_path = self.root / "config" / "settings.toml"
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        settings_path.write_text('theme = "light"\n', encoding="utf-8")

        manifest_path = self.root / "app.toml"
        manifest_path.write_text(
            """
version = 2

[resources.settings]
path = "config/settings.toml"
kind = "file"
role = "config"
readonly = true
""".strip(),
            encoding="utf-8",
        )

        manager = Coryl(self.root, manifest_path="app.toml")

        self.assertEqual(manager.configs.get("settings").load(), {"theme": "light"})
        with self.assertRaises(CorylReadOnlyResourceError):
            manager.configs.get("settings").save({"theme": "dark"})

    def test_audit_paths_returns_expected_structure(self) -> None:
        manifest_path = self.root / "app.yaml"
        manifest_path.write_text(
            """
version: 2
resources:
  settings:
    path: config/settings.toml
    kind: file
    role: config
    create: true
  http_cache:
    path: .cache/http
    kind: directory
    role: cache
    create: false
    backend: diskcache
  ui:
    path: assets/ui
    kind: directory
    role: assets
""".strip(),
            encoding="utf-8",
        )

        app = Coryl(self.root, manifest_path="app.yaml")
        audit = app.audit_paths()

        self.assertEqual(audit["root"], str(self.root.resolve()))
        self.assertEqual(
            audit["resources"]["settings"],
            {
                "path": str((self.root / "config" / "settings.toml").resolve()),
                "exists": True,
                "kind": "file",
                "role": "config",
                "safe": True,
            },
        )
        self.assertEqual(
            audit["resources"]["http_cache"],
            {
                "path": str((self.root / ".cache" / "http").resolve()),
                "exists": False,
                "kind": "directory",
                "role": "cache",
                "safe": True,
            },
        )

    def test_cache_namespace_helpers(self) -> None:
        manager = Coryl(self.root)
        cache = manager.caches.add("http_cache", ".cache/http")

        cache.remember("users", "42.json", content={"id": 42, "name": "Ada"})
        cache.remember("tokens", "state.txt", content="ready")

        self.assertEqual(cache.load("users", "42.json")["name"], "Ada")
        self.assertEqual(cache.load("tokens", "state.txt"), "ready")

        cache.delete("tokens", "state.txt", missing_ok=False)
        self.assertFalse(cache.file("tokens", "state.txt").exists())

        cache.clear()
        self.assertEqual(list(cache.iterdir()), [])

    def test_readonly_cache_cannot_clear_or_delete(self) -> None:
        cache_file = self.root / ".cache" / "http" / "users" / "42.json"
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_text('{"id": 42}', encoding="utf-8")

        manager = Coryl(self.root)
        cache = manager.register_cache("http_cache", ".cache/http", readonly=True)

        self.assertEqual(cache.load("users", "42.json")["id"], 42)

        with self.assertRaises(CorylReadOnlyResourceError):
            cache.delete("users", "42.json")

        with self.assertRaises(CorylReadOnlyResourceError):
            cache.clear()

    def test_asset_namespace_helpers(self) -> None:
        manager = Coryl(self.root)
        assets = manager.assets.add("ui", "assets")

        logo = assets.file("images", "logo.svg", create=True)
        logo.write_text("<svg></svg>")
        icons = assets.directory("icons", create=True)
        icons.file("check.svg", create=True).write_text("<svg></svg>")

        self.assertEqual(assets.require("images", "logo.svg").path.name, "logo.svg")
        self.assertTrue(assets.require("icons", kind="directory").path.is_dir())
        self.assertEqual(len(assets.files("**/*.svg")), 2)

    def test_package_assets_can_read_text_and_bytes(self) -> None:
        with self._test_asset_package() as package_name:
            manager = Coryl(self.root)
            assets = manager.assets.from_package("bundled", package_name, "assets")

            self.assertIsInstance(assets, PackageAssetGroup)
            self.assertEqual(
                assets.read_text("templates", "email.html"),
                "<html>Hello from Coryl</html>",
            )
            self.assertEqual(
                assets.read_bytes("images", "logo.bin"),
                b"\x00\x01coryl",
            )

            template = assets.file("templates", "email.html")
            self.assertIsInstance(template, PackageAssetResource)
            with template.as_file() as materialized_path:
                self.assertTrue(materialized_path.is_file())
                self.assertEqual(
                    materialized_path.read_text(encoding="utf-8"),
                    "<html>Hello from Coryl</html>",
                )

    def test_package_assets_require_raises_for_missing_resources(self) -> None:
        with self._test_asset_package() as package_name:
            manager = Coryl(self.root)
            assets = manager.assets.from_package("bundled", package_name, "assets")

            with self.assertRaises(FileNotFoundError):
                assets.require("missing.txt")

    def test_package_assets_are_readonly_and_can_be_bootstrapped(self) -> None:
        with self._test_asset_package() as package_name:
            manager = Coryl(self.root)
            assets = manager.assets.package("bundled", package_name, "assets")
            template = assets.require("templates", "email.html")

            self.assertTrue(assets.readonly)
            self.assertIsInstance(template, PackageAssetResource)
            self.assertTrue(template.readonly)

            with self.assertRaises(CorylReadOnlyResourceError):
                template.write_text("updated")

            with self.assertRaises(CorylPathError):
                _ = assets.path

            copied_root = assets.copy_to(self.root / "bootstrap")
            self.assertEqual(
                (copied_root / "templates" / "email.html").read_text(encoding="utf-8"),
                "<html>Hello from Coryl</html>",
            )
            self.assertEqual(
                (copied_root / "images" / "logo.bin").read_bytes(),
                b"\x00\x01coryl",
            )

    def test_child_paths_cannot_escape_parent(self) -> None:
        manager = Coryl(
            self.root,
            resources={"assets": ResourceSpec.assets("assets")},
        )
        assets = manager.assets.get("assets")
        image = assets.file("images", "logo.png", create=True)

        self.assertTrue(image.path.is_file())

        with self.assertRaises(CorylUnsafePathError):
            assets.file("images", "..", "escape.txt")

    def test_child_helpers_reject_absolute_paths(self) -> None:
        manager = Coryl(self.root)
        assets = manager.assets.add("ui", "assets")

        with self.assertRaises(CorylPathError):
            assets.file(self.root / "assets" / "logo.svg")

    def test_child_helpers_reject_directory_links_that_escape_parent(self) -> None:
        manager = Coryl(self.root)
        assets = manager.assets.add("ui", "assets")
        link_path = assets.path / "linked"
        self._make_directory_link(link_path, self.outside_root)

        with self.assertRaises(CorylUnsafePathError):
            assets.file("linked", "secret.txt")

    def test_rejects_invalid_kind(self) -> None:
        manager = Coryl(self.root)

        with self.assertRaises(CorylInvalidResourceKindError):
            manager.register("invalid", {"path": "runtime/item", "kind": "socket"})

    def test_resource_validation_errors_are_explicit(self) -> None:
        manager = Coryl(self.root, resources={"assets": ResourceSpec.directory("assets")})

        with self.assertRaises(ResourceNotRegisteredError):
            manager.path("missing")

        with self.assertRaises(ResourceKindError):
            manager.file("assets")

        with self.assertRaises(ResourceKindError):
            manager.configs.get("assets")

    @contextmanager
    def _test_asset_package(self) -> Iterator[str]:
        package_name = "coryl_testpkg"
        package_root = self.root / "package_src" / package_name
        templates_root = package_root / "assets" / "templates"
        images_root = package_root / "assets" / "images"
        templates_root.mkdir(parents=True, exist_ok=True)
        images_root.mkdir(parents=True, exist_ok=True)
        (package_root / "__init__.py").write_text("", encoding="utf-8")
        (templates_root / "email.html").write_text(
            "<html>Hello from Coryl</html>",
            encoding="utf-8",
        )
        (images_root / "logo.bin").write_bytes(b"\x00\x01coryl")

        sys.path.insert(0, str(package_root.parent))
        importlib.invalidate_caches()
        sys.modules.pop(package_name, None)
        try:
            yield package_name
        finally:
            sys.modules.pop(package_name, None)
            importlib.invalidate_caches()
            sys.path.remove(str(package_root.parent))

    def _make_directory_link(self, link_path: Path, target_path: Path) -> None:
        self._directory_links.append(link_path)
        if os.name == "nt":
            result = subprocess.run(
                ["cmd", "/c", "mklink", "/J", str(link_path), str(target_path)],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode != 0:
                raise unittest.SkipTest(result.stderr.strip() or result.stdout.strip())
            return

        try:
            link_path.symlink_to(target_path, target_is_directory=True)
        except OSError as error:
            raise unittest.SkipTest(f"Directory symlinks are unavailable: {error}") from error

    def _remove_directory_link(self, link_path: Path) -> None:
        if not link_path.exists() and not link_path.is_symlink():
            return

        if os.name == "nt":
            subprocess.run(
                ["cmd", "/c", "rmdir", str(link_path)],
                capture_output=True,
                text=True,
                check=False,
            )
            return

        link_path.unlink()

    def _temporary_files_for(self, destination: Path) -> list[Path]:
        prefix = f".{destination.name}."
        return sorted(
            candidate
            for candidate in destination.parent.iterdir()
            if candidate.name.startswith(prefix) and candidate.name.endswith(".tmp")
        )

    def _make_fake_lock_backend(self) -> tuple[type[object], type[BaseException]]:
        class FakeTimeout(Exception):
            pass

        class FakeAcquire:
            def __init__(self, lock_path: Path) -> None:
                self._lock_path = lock_path

            def __enter__(self) -> Path:
                self._lock_path.write_text("locked", encoding="utf-8")
                return self._lock_path

            def __exit__(self, exc_type: object, exc: object, traceback: object) -> bool:
                return False

        class FakeFileLock:
            created_paths: list[Path] = []
            requested_timeouts: list[float | None] = []

            def __init__(self, lock_path: str) -> None:
                self._lock_path = Path(lock_path)
                type(self).created_paths.append(self._lock_path)

            def acquire(self, timeout: float | None = None) -> FakeAcquire:
                type(self).requested_timeouts.append(timeout)
                return FakeAcquire(self._lock_path)

        return FakeFileLock, FakeTimeout

    def _make_timeout_lock_backend(self) -> tuple[type[object], type[BaseException]]:
        class FakeTimeout(Exception):
            pass

        class FakeFileLock:
            def __init__(self, lock_path: str) -> None:
                self._lock_path = Path(lock_path)

            def acquire(self, timeout: float | None = None) -> object:
                raise FakeTimeout(f"timeout for {self._lock_path}")

        return FakeFileLock, FakeTimeout

    def _make_fake_platformdirs_module(
        self,
        platform_roots: dict[str, Path],
    ) -> tuple[types.SimpleNamespace, list[dict[str, object]]]:
        calls: list[dict[str, object]] = []

        class FakePlatformDirs:
            def __init__(
                self,
                *,
                appname: str | None = None,
                appauthor: str | None = None,
                version: str | None = None,
                roaming: bool = False,
                multipath: bool = False,
                ensure_exists: bool = False,
            ) -> None:
                calls.append(
                    {
                        "appname": appname,
                        "appauthor": appauthor,
                        "version": version,
                        "roaming": roaming,
                        "multipath": multipath,
                        "ensure_exists": ensure_exists,
                    }
                )
                self.user_config_path = platform_roots["config"]
                self.user_cache_path = platform_roots["cache"]
                self.user_data_path = platform_roots["data"]
                self.user_log_path = platform_roots["log"]
                if ensure_exists:
                    for path in platform_roots.values():
                        path.mkdir(parents=True, exist_ok=True)

        return types.SimpleNamespace(PlatformDirs=FakePlatformDirs), calls

    def _make_fake_pydantic_module(self) -> types.SimpleNamespace:
        class FakeValidationError(Exception):
            pass

        class FakeBaseModel:
            @classmethod
            def model_validate(cls, data: object) -> object:
                raise NotImplementedError

        class SettingsModel(FakeBaseModel):
            def __init__(self, host: str, port: int, debug: bool = False) -> None:
                self.host = host
                self.port = port
                self.debug = debug

            @classmethod
            def model_validate(cls, data: object) -> "SettingsModel":
                if not isinstance(data, dict):
                    raise FakeValidationError("Input should be a mapping.")

                host = data.get("host")
                port = data.get("port")
                debug = data.get("debug", False)
                if not isinstance(host, str):
                    raise FakeValidationError("host must be a string.")
                if not isinstance(port, int):
                    raise FakeValidationError("port must be an integer.")
                if not isinstance(debug, bool):
                    raise FakeValidationError("debug must be a boolean.")
                return cls(host, port, debug)

            def model_dump(self, *, mode: str = "python") -> dict[str, object]:
                if mode != "json":
                    raise AssertionError(f"Unexpected dump mode: {mode!r}")
                return {
                    "host": self.host,
                    "port": self.port,
                    "debug": self.debug,
                }

        return types.SimpleNamespace(
            BaseModel=FakeBaseModel,
            ValidationError=FakeValidationError,
            SettingsModel=SettingsModel,
        )


if __name__ == "__main__":
    unittest.main()
