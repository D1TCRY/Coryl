from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from coryl import (
    AssetGroup,
    CacheResource,
    ConfigResource,
    Coryl,
    ResourceKindError,
    ResourceNotRegisteredError,
    ResourceSpec,
    UnsafePathError,
)


class CorylTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

    def tearDown(self) -> None:
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

    def test_json_round_trip_and_legacy_aliases(self) -> None:
        manager = Coryl(self.root)
        manager.register_file("data", "storage/data.json")

        manager.write_content("data", {"name": "Coryl", "version": 1})

        self.assertEqual(manager.content("data"), {"name": "Coryl", "version": 1})
        self.assertEqual(manager.data_file_path.name, "data.json")
        with self.assertRaises(AttributeError):
            _ = manager.data_directory_path

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

    def test_legacy_manifest_schema_is_supported(self) -> None:
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

        self.assertTrue(manager.settings_file_path.is_file())
        self.assertTrue(manager.cache_directory_path.is_dir())
        self.assertIn("paths", manager.config)

    def test_toml_manifest_with_specialized_roles(self) -> None:
        manifest_path = self.root / "app.toml"
        manifest_path.write_text(
            """
[resources.settings]
path = "config/settings.toml"
kind = "file"
role = "config"

[resources.http_cache]
path = ".cache/http"
kind = "directory"
role = "cache"

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

    def test_modern_manifest_schema_can_be_reloaded(self) -> None:
        manifest_path = self.root / "app.yaml"
        manifest_path.write_text(
            """
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

    def test_prevents_escaping_the_root_folder(self) -> None:
        manager = Coryl(self.root)
        with self.assertRaises(UnsafePathError):
            manager.register_file("secrets", "../secrets.json")

    def test_directory_helpers_stay_safe(self) -> None:
        manager = Coryl(
            self.root,
            resources={"assets": ResourceSpec.assets("assets")},
        )

        image = manager.assets.get("assets").file("images", "logo.png", create=True)
        self.assertTrue(image.path.is_file())

        with self.assertRaises(UnsafePathError):
            manager.assets.get("assets").file("..", "escape.txt")

    def test_resource_validation_errors_are_explicit(self) -> None:
        manager = Coryl(self.root, resources={"assets": ResourceSpec.directory("assets")})

        with self.assertRaises(ResourceNotRegisteredError):
            manager.path("missing")

        with self.assertRaises(ResourceKindError):
            manager.file("assets")

        with self.assertRaises(ResourceKindError):
            manager.configs.get("assets")


if __name__ == "__main__":
    unittest.main()
