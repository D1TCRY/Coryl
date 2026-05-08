"""Simple local app example."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from coryl import Coryl


with TemporaryDirectory() as temp_dir:
    root = Path(temp_dir)
    (root / "assets" / "ui" / "images").mkdir(parents=True, exist_ok=True)
    (root / "assets" / "ui" / "images" / "logo.svg").write_text(
        "<svg></svg>",
        encoding="utf-8",
    )

    app = Coryl(root=root)

    settings = app.configs.add("settings", "config/settings.toml")
    cache = app.caches.add("http", ".cache/http")
    assets = app.assets.add("ui", "assets/ui")

    settings.save({"app_name": "Coryl Demo", "debug": True})
    user = cache.remember_json(
        "users/42.json",
        lambda: {"id": 42, "name": "Ada"},
        ttl=300,
    )
    logo = assets.require("images", "logo.svg")

    print(settings.load()["app_name"])
    print(user["name"])
    print(logo.path.name)

