"""Optional fsspec memory example."""

from __future__ import annotations

from importlib.util import find_spec
from pathlib import Path
import sys
from uuid import uuid4

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
    if find_spec("fsspec") is None:
        return emit_json(
            {
                "available": False,
                "reason": "fsspec is not installed.",
                "skipped": True,
            }
        )

    configured_root = f"memory://coryl-example-{uuid4().hex}"
    app = Coryl.with_fs(
        root=configured_root,
        protocol="memory",
    )
    settings = app.configs.add("settings", "config/settings.json")
    cache = app.caches.add("api", ".cache/api")
    assets = app.assets.add("ui", "assets/ui")

    settings.save({"theme": "light", "debug": True})
    logo = assets.file("images", "logo.txt", create=True)
    logo.write_text("logo")

    calls = {"count": 0}

    def build_user() -> dict[str, object]:
        calls["count"] += 1
        return {"id": 42, "call": calls["count"]}

    first = cache.remember_json("users/42.json", build_user)
    second = cache.remember_json("users/42.json", build_user)

    return emit_json(
        {
            "available": True,
            "configured_root": configured_root,
            "factory_calls": calls["count"],
            "first": first,
            "logo_text": assets.require("images", "logo.txt").read_text(),
            "root": app.root_path.as_posix(),
            "second": second,
            "settings": settings.load(),
        }
    )


if __name__ == "__main__":
    raise SystemExit(main())
