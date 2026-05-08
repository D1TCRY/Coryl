"""Layered config example."""

from __future__ import annotations

import os
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

from _support import emit_json, ensure_src_path, write_block

ensure_src_path()

from coryl import Coryl


def main() -> int:
    with TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        write_block(
            root / "config" / "defaults.toml",
            """
            debug = false
            theme = "base"

            [database]
            host = "db"
            port = 5432
            """,
        )
        write_block(
            root / "config" / "local.toml",
            """
            theme = "local"
            """,
        )

        previous_host = os.environ.get("MYAPP_DATABASE__HOST")
        os.environ["MYAPP_DATABASE__HOST"] = "env-db"
        payload: dict[str, object]
        try:
            app = Coryl(root=root)
            settings = app.configs.layered(
                "settings",
                files=[
                    "config/defaults.toml",
                    "config/local.toml",
                ],
                env_prefix="MYAPP",
            )

            merged = settings.override({"debug": True})
            payload = {
                "database_host": settings.get("database.host"),
                "debug": merged["debug"],
                "merged": merged,
            }
        finally:
            if previous_host is None:
                os.environ.pop("MYAPP_DATABASE__HOST", None)
            else:
                os.environ["MYAPP_DATABASE__HOST"] = previous_host

        return emit_json(payload)


if __name__ == "__main__":
    raise SystemExit(main())
