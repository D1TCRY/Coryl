"""Bundled package assets example.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

from coryl import Coryl


with TemporaryDirectory() as temp_dir:
    root = Path(temp_dir)
    package_name = "coryl_example_pkg"
    package_root = root / package_name
    templates_root = package_root / "assets" / "templates"
    templates_root.mkdir(parents=True, exist_ok=True)
    (package_root / "__init__.py").write_text("", encoding="utf-8")
    (templates_root / "email.html").write_text(
        "<html>Hello from Coryl</html>",
        encoding="utf-8",
    )

    sys.path.insert(0, str(root))
    importlib.invalidate_caches()
    sys.modules.pop(package_name, None)
    try:
        app = Coryl(root=root)
        assets = app.assets.from_package("templates", package_name, "assets/templates")
        template = assets.file("email.html")

        print(assets.read_text("email.html"))
        with template.as_file() as path:
            print(path.name)
    finally:
        sys.modules.pop(package_name, None)
        importlib.invalidate_caches()
        sys.path.remove(str(root))
