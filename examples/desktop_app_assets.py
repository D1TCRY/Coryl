"""Desktop app asset example using filesystem and package assets."""

from __future__ import annotations

import importlib
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
        write_text(root / "assets" / "ui" / "icons" / "app.svg", "<svg>app</svg>")

        package_name = "coryl_desktop_assets_pkg"
        package_root = root / package_name
        write_text(package_root / "__init__.py", "")
        write_text(
            package_root / "assets" / "templates" / "welcome.html",
            "<html>Welcome</html>",
        )

        sys.path.insert(0, str(root))
        importlib.invalidate_caches()
        sys.modules.pop(package_name, None)
        try:
            app = Coryl(root=root)
            filesystem_assets = app.assets.add("desktop_ui", "assets/ui", readonly=True)
            package_assets = app.assets.from_package("bundled", package_name, "assets")
            local_logo = filesystem_assets.require("icons", "app.svg")

            return emit_json(
                {
                    "local_logo_name": local_logo.path.name,
                    "local_logo_text": local_logo.read_text(),
                    "package_files": [
                        resource.relative_path.as_posix()
                        for resource in package_assets.files("**/*")
                    ],
                    "package_template": package_assets.read_text(
                        "templates", "welcome.html"
                    ),
                }
            )
        finally:
            sys.modules.pop(package_name, None)
            importlib.invalidate_caches()
            sys.path.remove(str(root))


if __name__ == "__main__":
    raise SystemExit(main())
