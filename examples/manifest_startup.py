"""Manifest startup example."""

from __future__ import annotations

from pathlib import Path
import sys
from tempfile import TemporaryDirectory

EXAMPLES_DIR = (
    Path(__file__).resolve().parent
    if "__file__" in globals()
    else Path.cwd() / "examples"
)
if str(EXAMPLES_DIR) not in sys.path:
    sys.path.insert(0, str(EXAMPLES_DIR))

from _support import emit_json, ensure_src_path, write_block, write_text

ensure_src_path()

from coryl import Coryl


def main() -> int:
    with TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        write_block(
            root / "app.toml",
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
            """,
        )
        write_block(
            root / "config" / "settings.toml",
            """
            theme = "dark"

            [database]
            host = "localhost"
            port = 5432
            """,
        )
        write_text(root / ".cache" / "http" / "users" / "42.json", '{"id": 42}')
        write_text(root / "assets" / "ui" / "logo.svg", "<svg></svg>")

        app = Coryl(root=root, manifest_path="app.toml", create_missing=False)
        audit = app.audit_paths()
        settings = app.configs.get("settings")
        cache = app.caches.get("http_cache")
        assets = app.assets.get("ui")

        return emit_json(
            {
                "audit_paths": audit,
                "cached_user": cache.load("users", "42.json"),
                "logo_name": assets.require("logo.svg").path.name,
                "resource_names": sorted(audit["resources"]),
                "theme": settings.get("theme"),
            }
        )


if __name__ == "__main__":
    raise SystemExit(main())
