from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from coryl.cli import main


class CorylCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_resources_list_command_lists_manifest_resources(self) -> None:
        self._write_manifest(
            """
            version = 2

            [resources.settings]
            path = "config/settings.toml"
            kind = "file"
            role = "config"
            create = false

            [resources.http_cache]
            path = ".cache/http"
            kind = "directory"
            role = "cache"
            create = false

            [resources.ui]
            path = "assets/ui"
            kind = "directory"
            role = "assets"
            create = false
            """
        )
        (self.root / "config").mkdir(parents=True, exist_ok=True)
        (self.root / "config" / "settings.toml").write_text('theme = "dark"\n', encoding="utf-8")
        (self.root / ".cache" / "http").mkdir(parents=True, exist_ok=True)
        (self.root / "assets" / "ui").mkdir(parents=True, exist_ok=True)

        code, stdout, stderr = self._run_cli("resources", "list")

        self.assertEqual(code, 0)
        self.assertEqual(stderr, "")
        self.assertIn("settings", stdout)
        self.assertIn("http_cache", stdout)
        self.assertIn("ui", stdout)
        self.assertIn("settings.toml", stdout)

    def test_resources_check_detects_missing_resources(self) -> None:
        self._write_manifest(
            """
            version = 2

            [resources.settings]
            path = "config/settings.toml"
            kind = "file"
            role = "config"
            create = false

            [resources.ui]
            path = "assets/ui"
            kind = "directory"
            role = "assets"
            create = false
            """
        )
        (self.root / "assets" / "ui").mkdir(parents=True, exist_ok=True)

        code, stdout, stderr = self._run_cli("resources", "check")

        self.assertEqual(code, 1)
        self.assertEqual(stderr, "")
        self.assertIn("settings", stdout)
        self.assertIn("missing", stdout)

    def test_config_show_prints_config_resource(self) -> None:
        self._write_manifest(
            """
            version = 2

            [resources.settings]
            path = "config/settings.toml"
            kind = "file"
            role = "config"
            create = false
            """
        )
        settings_path = self.root / "config" / "settings.toml"
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        settings_path.write_text(
            'theme = "dark"\n[database]\nhost = "localhost"\nport = 5432\n',
            encoding="utf-8",
        )

        code, stdout, stderr = self._run_cli("config", "show", "settings")

        self.assertEqual(code, 0)
        self.assertEqual(stderr, "")
        self.assertIn("theme", stdout)
        self.assertIn("dark", stdout)
        self.assertIn("database", stdout)

    def test_cache_clear_clears_selected_cache(self) -> None:
        self._write_manifest(
            """
            version = 2

            [resources.http_cache]
            path = ".cache/http"
            kind = "directory"
            role = "cache"
            create = false
            """
        )
        cache_file = self.root / ".cache" / "http" / "users" / "42.json"
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_text('{"id": 42}\n', encoding="utf-8")

        code, stdout, stderr = self._run_cli("cache", "clear", "http_cache")

        self.assertEqual(code, 0)
        self.assertEqual(stderr, "")
        self.assertIn("http_cache", stdout)
        self.assertEqual(list((self.root / ".cache" / "http").iterdir()), [])

    def test_json_output_is_valid(self) -> None:
        self._write_manifest(
            """
            version = 2

            [resources.settings]
            path = "config/settings.toml"
            kind = "file"
            role = "config"
            create = false
            """
        )
        settings_path = self.root / "config" / "settings.toml"
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        settings_path.write_text('theme = "dark"\n', encoding="utf-8")

        code, stdout, stderr = self._run_cli("resources", "list", "--json")

        self.assertEqual(code, 0)
        self.assertEqual(stderr, "")
        payload = json.loads(stdout)
        self.assertIn("root", payload)
        self.assertEqual(payload["resources"][0]["name"], "settings")
        self.assertTrue(payload["resources"][0]["exists"])

    def _run_cli(self, *args: str) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        code = main(
            [*args, "--manifest", "app.toml", "--root", str(self.root)],
            stdout=stdout,
            stderr=stderr,
        )
        return code, stdout.getvalue(), stderr.getvalue()

    def _write_manifest(self, content: str) -> None:
        manifest_path = self.root / "app.toml"
        manifest_path.write_text(content.strip() + "\n", encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
