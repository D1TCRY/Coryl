from __future__ import annotations

import importlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

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

    def test_package_assets_are_readonly_by_default(self) -> None:
        package_name = "coryl_testpkg"
        package_root = self.root / "package_src" / package_name
        assets_root = package_root / "assets" / "icons"
        assets_root.mkdir(parents=True, exist_ok=True)
        (package_root / "__init__.py").write_text("", encoding="utf-8")
        (assets_root / "logo.svg").write_text("<svg></svg>", encoding="utf-8")

        sys.path.insert(0, str(package_root.parent))
        importlib.invalidate_caches()
        sys.modules.pop(package_name, None)
        try:
            manager = Coryl(self.root)
            assets = manager.assets.package("pkg_assets", package_name, "assets")
            logo = assets.require("icons", "logo.svg")

            self.assertTrue(assets.readonly)
            self.assertTrue(logo.readonly)
            self.assertEqual(logo.read_text(), "<svg></svg>")

            with self.assertRaises(CorylReadOnlyResourceError):
                logo.write_text("<svg>changed</svg>")
        finally:
            sys.modules.pop(package_name, None)
            importlib.invalidate_caches()
            sys.path.remove(str(package_root.parent))

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


if __name__ == "__main__":
    unittest.main()
