"""CLI tool config example."""

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

from _support import emit_json, ensure_src_path

ensure_src_path()

from coryl import Coryl


def main() -> int:
    with TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        app = Coryl(root=root)
        settings = app.configs.add("settings", "config/tool.json", create=False)

        created_default = False
        if not settings.exists():
            settings.save({"theme": "light", "retries": 2})
            created_default = True

        updated = settings.update(theme="dark", retries=3)

        return emit_json(
            {
                "created_default": created_default,
                "retries": updated["retries"],
                "value": updated["theme"],
            }
        )


if __name__ == "__main__":
    raise SystemExit(main())
