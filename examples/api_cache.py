"""File-oriented API cache example."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from coryl import Coryl


with TemporaryDirectory() as temp_dir:
    root = Path(temp_dir)
    app = Coryl(root=root)
    cache = app.caches.add("api", ".cache/api")

    user = cache.remember_json(
        "users/42.json",
        lambda: {"id": 42, "name": "Ada"},
        ttl=300,
    )
    state = cache.remember_text("tokens/state.txt", lambda: "ready", ttl=60)

    print(user["name"])
    print(state)
