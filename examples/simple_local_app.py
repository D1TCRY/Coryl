"""Simple local app example."""

from __future__ import annotations

import sys
from pathlib import Path
from tempfile import TemporaryDirectory

EXAMPLES_DIR = (
    Path(__file__).resolve().parent
    if "__file__" in globals()
    else Path.cwd() / "examples"
)
if str(EXAMPLES_DIR) not in sys.path:
    sys.path.insert(0, str(EXAMPLES_DIR))

from _support import emit_json, ensure_src_path, write_text

ensure_src_path()

from coryl import Coryl


def main() -> int:
    with TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        write_text(root / "assets" / "ui" / "logo.svg", "<svg>demo</svg>")

        app = Coryl(root=root)
        settings = app.configs.add("settings", "config/settings.toml")
        profile = app.configs.add("profile", "config/profile.json")
        cache = app.caches.add("people", ".cache/people")
        assets = app.assets.add("ui", "assets/ui")

        settings.save({"app_name": "Coryl Demo", "debug": True})
        profile.save({"locale": "en-US", "timezone": "UTC"})
        user = cache.remember_json(
            "users/ada.json",
            lambda: {"id": 1, "name": "Ada"},
        )
        logo = assets.require("logo.svg")

        return emit_json(
            {
                "app_name": settings.load()["app_name"],
                "cached_user": user,
                "debug": settings.load()["debug"],
                "locale": profile.load()["locale"],
                "logo_name": logo.path.name,
            }
        )


if __name__ == "__main__":
    raise SystemExit(main())
