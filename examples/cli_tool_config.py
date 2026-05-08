"""CLI tool config example."""

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
    typed_schema: type[object] | None = None
    if find_spec("pydantic") is not None:
        from pydantic import BaseModel

        if hasattr(BaseModel, "model_validate"):
            class CliSettings(BaseModel):
                theme: str
                verbose: bool
                retries: int

            typed_schema = CliSettings

    with TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        app = Coryl(root=root)

        settings = app.configs.add(
            "settings",
            "config/settings.toml",
            create=False,
            schema=typed_schema,
        )
        cache = app.caches.add("http", ".cache/http")

        created_default = False
        if not settings.exists():
            settings.save({"theme": "light", "verbose": False, "retries": 2})
            created_default = True

        updated = settings.update(theme="dark", verbose=True)
        session = cache.remember_text("tokens/session.txt", lambda: "ready", ttl=60)

        typed_payload: dict[str, object] = {"available": False}
        if typed_schema is not None:
            typed_settings = settings.load_typed()
            typed_payload = {
                "available": True,
                "retries": typed_settings.retries,
                "theme": typed_settings.theme,
                "verbose": typed_settings.verbose,
            }

        return emit_json(
            {
                "created_default": created_default,
                "session_state": session,
                "settings": updated,
                "typed": typed_payload,
            }
        )


if __name__ == "__main__":
    raise SystemExit(main())
