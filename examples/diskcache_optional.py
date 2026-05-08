"""Optional diskcache example."""

from __future__ import annotations

from importlib.util import find_spec
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

EXAMPLES_DIR = Path(__file__).resolve().parent if "__file__" in globals() else Path.cwd() / "examples"
if str(EXAMPLES_DIR) not in sys.path:
    sys.path.insert(0, str(EXAMPLES_DIR))

from _support import emit_json, ensure_src_path

ensure_src_path()

from coryl import Coryl


def main() -> int:
    if find_spec("diskcache") is None:
        return emit_json(
            {
                "available": False,
                "reason": "diskcache is not installed.",
                "skipped": True,
            }
        )

    with TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        app = Coryl(root=root)
        cache = app.caches.diskcache("api", ".cache/api")
        cache.set("users/42", {"id": 42, "name": "Ada"})
        first = cache.remember_json("responses/user.json", lambda: {"id": 7, "call": 1}, ttl=60)
        second = cache.remember_json("responses/user.json", lambda: {"id": 7, "call": 2}, ttl=60)

        return emit_json(
            {
                "available": True,
                "cached_user": cache.get("users/42"),
                "first": first,
                "second": second,
            }
        )


if __name__ == "__main__":
    raise SystemExit(main())
