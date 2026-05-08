"""CLI tool config example."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from coryl import Coryl


with TemporaryDirectory() as temp_dir:
    root = Path(temp_dir)
    app = Coryl(root=root)

    settings = app.configs.add("settings", "config/cli.toml")
    cache = app.caches.add("http", ".cache/http")

    settings.save({"theme": "dark", "verbose": False})
    session = cache.remember_text("tokens/session.txt", lambda: "ready", ttl=60)

    print(settings.load()["theme"])
    print(session)

