"""Diagnostics CLI example."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

EXAMPLES_DIR = Path(__file__).resolve().parent if "__file__" in globals() else Path.cwd() / "examples"
if str(EXAMPLES_DIR) not in sys.path:
    sys.path.insert(0, str(EXAMPLES_DIR))

from _support import emit_json, ensure_src_path, pythonpath_env, write_block, write_text

ensure_src_path()


def _run_cli(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "coryl.cli", *args],
        capture_output=True,
        check=False,
        cwd=root,
        env=pythonpath_env(),
        text=True,
    )


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

        listed = _run_cli(root, "resources", "list", "--manifest", "app.toml", "--root", ".", "--json")
        checked = _run_cli(root, "resources", "check", "--manifest", "app.toml", "--root", ".", "--json")
        shown = _run_cli(root, "config", "show", "settings", "--manifest", "app.toml", "--root", ".", "--json")

        return emit_json(
            {
                "config_show": json.loads(shown.stdout),
                "resources_check": json.loads(checked.stdout),
                "resources_list": json.loads(listed.stdout),
                "returncodes": {
                    "check": checked.returncode,
                    "list": listed.returncode,
                    "show": shown.returncode,
                },
            }
        )


if __name__ == "__main__":
    raise SystemExit(main())
