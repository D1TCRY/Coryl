"""API cache example."""

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
        cache = app.caches.add("api", ".cache/api")

        calls = {"count": 0}

        def fake_api() -> dict[str, object]:
            calls["count"] += 1
            return {"call": calls["count"], "id": 42, "name": "Ada"}

        first = cache.remember_json("users/42.json", fake_api, ttl=60)
        second = cache.remember_json("users/42.json", fake_api, ttl=60)

        return emit_json(
            {
                "factory_calls": calls["count"],
                "first": first,
                "second": second,
            }
        )


if __name__ == "__main__":
    raise SystemExit(main())
