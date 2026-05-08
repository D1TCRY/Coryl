"""File-oriented API cache example."""

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

import coryl.resources as coryl_resources

from coryl import Coryl


def main() -> int:
    with TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        app = Coryl(root=root)
        cache = app.caches.add("api", ".cache/api")

        clock = {"now": 1_000.0}
        calls = {"count": 0}
        original_time = coryl_resources.time.time
        coryl_resources.time.time = lambda: clock["now"]
        try:

            def fetch_user() -> dict[str, object]:
                calls["count"] += 1
                return {"id": 42, "etag": f"v{calls['count']}"}

            first = cache.remember_json("users/42.json", fetch_user, ttl=10)
            second = cache.remember_json("users/42.json", fetch_user, ttl=10)

            clock["now"] = 1_011.0
            expired_value = cache.load("users", "42.json", default="expired")
            third = cache.remember_json("users/42.json", fetch_user, ttl=10)
        finally:
            coryl_resources.time.time = original_time

        return emit_json(
            {
                "expired_value": expired_value,
                "factory_calls": calls["count"],
                "first": first,
                "second": second,
                "third": third,
            }
        )


if __name__ == "__main__":
    raise SystemExit(main())
