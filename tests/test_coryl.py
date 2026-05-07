from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from coryl import (
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

    def test_modern_manifest_schema_can_be_reloaded(self) -> None:
        manifest_path = self.root / "app.json"
        manifest_path.write_text(
            json.dumps(
                {
                    "resources": {
                        "settings": {"path": "config/settings.json", "kind": "file"},
                        "assets": {"path": "assets", "kind": "directory"},
                    }
                }
            ),
            encoding="utf-8",
        )

        manager = Coryl(self.root, manifest_path=manifest_path)
        self.assertTrue(manager.settings_file_path.is_file())
        self.assertTrue(manager.assets_directory_path.is_dir())

        manifest_path.write_text(
            json.dumps(
                {
                    "resources": {
                        "settings": {"path": "config/new-settings.json", "kind": "file"}
                    }
                }
            ),
            encoding="utf-8",
        )

        manager.load_config()
        self.assertEqual(manager.settings_file_path.name, "new-settings.json")
        with self.assertRaises(AttributeError):
            _ = manager.assets_directory_path

    def test_prevents_escaping_the_root_folder(self) -> None:
        manager = Coryl(self.root)
        with self.assertRaises(UnsafePathError):
            manager.register_file("secrets", "../secrets.json")

    def test_directory_helpers_stay_safe(self) -> None:
        manager = Coryl(
            self.root,
            resources={"assets": ResourceSpec.directory("assets")},
        )

        image = manager.directory("assets").joinpath("images", "logo.png", create=True)
        self.assertTrue(image.path.is_file())

        with self.assertRaises(UnsafePathError):
            manager.directory("assets").joinpath("..", "escape.txt")

    def test_resource_validation_errors_are_explicit(self) -> None:
        manager = Coryl(self.root, resources={"assets": ResourceSpec.directory("assets")})

        with self.assertRaises(ResourceNotRegisteredError):
            manager.path("missing")

        with self.assertRaises(ResourceKindError):
            manager.file("assets")


if __name__ == "__main__":
    unittest.main()
