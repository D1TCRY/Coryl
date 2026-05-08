"""Desktop app asset example."""

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

from _support import emit_json, ensure_src_path, write_bytes, write_text

ensure_src_path()

from coryl import Coryl


def main() -> int:
    with TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        write_bytes(root / "assets" / "desktop" / "icons" / "app.ico", b"ICO")
        write_text(
            root / "assets" / "desktop" / "templates" / "window.html",
            "<main>Window</main>",
        )

        app = Coryl(root=root)
        assets = app.assets.add("desktop", "assets/desktop")
        icon = assets.require("icons", "app.ico")
        template = assets.require("templates", "window.html")

        return emit_json(
            {
                "files": [
                    path.relative_to(assets.path).as_posix()
                    for path in sorted(assets.files("**/*"))
                ],
                "glob_matches": [
                    path.relative_to(assets.path).as_posix()
                    for path in sorted(assets.glob("templates/*.html"))
                ],
                "icon_name": icon.path.name,
                "template_text": template.read_text(),
            }
        )


if __name__ == "__main__":
    raise SystemExit(main())
