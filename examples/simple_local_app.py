"""Simple local app example."""

from __future__ import annotations

import sys
from pathlib import Path
from tempfile import TemporaryDirectory

EXAMPLES_DIR = Path(__file__).resolve().parent if "__file__" in globals() else Path.cwd() / "examples"
if str(EXAMPLES_DIR) not in sys.path:
    sys.path.insert(0, str(EXAMPLES_DIR))

from _support import emit_json, ensure_src_path, write_text

ensure_src_path()

from coryl import Coryl


def main() -> int:
    with TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        write_text(root / "assets" / "ui" / "images" / "logo.svg", "<svg></svg>")

        app = Coryl(root=root)
        settings = app.configs.add("settings", "config/settings.toml")
        cache = app.caches.add("http", ".cache/http")
        assets = app.assets.add("ui", "assets/ui")
        profiles = app.data.add("profiles", "data/profiles.json")

        settings.save({"app_name": "Coryl Demo", "debug": True})
        profiles.write_json([{"id": 42, "name": "Ada"}])
        user = cache.remember_json(
            "users/42.json",
            lambda: {"id": 42, "name": "Ada"},
            ttl=300,
        )
        logo = assets.require("images", "logo.svg")

        return emit_json(
            {
                "app_name": settings.load()["app_name"],
                "cached_user": user,
                "debug": settings.load()["debug"],
                "logo_name": logo.path.name,
                "profiles_count": len(profiles.read_json()),
                "settings_path": settings.path.as_posix(),
            }
        )


if __name__ == "__main__":
    raise SystemExit(main())
