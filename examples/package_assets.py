"""Bundled package assets example."""

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
        package_name = "coryl_example_pkg"
        package_root = root / package_name
        templates_root = package_root / "assets" / "templates"
        write_text(package_root / "__init__.py", "")
        write_text(
            templates_root / "email.html",
            "<html>Hello from Coryl</html>",
        )

        sys.path.insert(0, str(root))
        importlib.invalidate_caches()
        sys.modules.pop(package_name, None)
        try:
            app = Coryl(root=root)
            assets = app.assets.from_package(
                "templates", package_name, "assets/templates"
            )
            template = assets.file("email.html")

            with template.as_file() as path:
                return emit_json(
                    {
                        "matched_files": [
                            resource.relative_path.as_posix()
                            for resource in assets.files("*")
                        ],
                        "materialized_name": path.name,
                        "template_text": assets.read_text("email.html"),
                    }
                )
        finally:
            sys.modules.pop(package_name, None)
            importlib.invalidate_caches()
            sys.path.remove(str(root))


if __name__ == "__main__":
    raise SystemExit(main())
