"""Package assets example."""

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

from _support import emit_json, ensure_src_path, write_bytes, write_text

ensure_src_path()

from coryl import Coryl


def main() -> int:
    with TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        package_name = "coryl_package_assets_demo"
        package_root = root / package_name
        write_text(package_root / "__init__.py", "")
        write_text(
            package_root / "assets" / "templates" / "welcome.txt",
            "Hello from package",
        )
        write_bytes(package_root / "assets" / "icons" / "app.bin", b"CORYL")

        sys.path.insert(0, str(root))
        importlib.invalidate_caches()
        sys.modules.pop(package_name, None)
        try:
            app = Coryl(root=root)
            assets = app.assets.from_package("bundled", package_name, "assets")
            copied_root = assets.copy_to(root / "copied-assets")

            return emit_json(
                {
                    "copied_files": [
                        path.relative_to(copied_root).as_posix()
                        for path in sorted(copied_root.rglob("*"))
                        if path.is_file()
                    ],
                    "icon_size": len(assets.read_bytes("icons", "app.bin")),
                    "template_text": assets.read_text("templates", "welcome.txt"),
                }
            )
        finally:
            sys.modules.pop(package_name, None)
            importlib.invalidate_caches()
            sys.path.remove(str(root))


if __name__ == "__main__":
    raise SystemExit(main())
