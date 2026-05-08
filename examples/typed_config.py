"""Typed config example."""

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
    try:
        from pydantic import BaseModel
    except ModuleNotFoundError:
        return emit_json(
            {
                "available": False,
                "reason": "pydantic is not installed.",
            }
        )

    if not hasattr(BaseModel, "model_validate"):
        return emit_json(
            {
                "available": False,
                "reason": "typed config helpers require Pydantic v2.",
            }
        )

    class SettingsModel(BaseModel):
        host: str
        port: int
        debug: bool = False

    with TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        app = Coryl(root=root)
        settings = app.configs.add(
            "settings", "config/settings.toml", schema=SettingsModel
        )
        settings.save_typed(SettingsModel(host="localhost", port=5432, debug=True))

        typed_settings = settings.load_typed()
        return emit_json(
            {
                "available": True,
                "debug": typed_settings.debug,
                "host": typed_settings.host,
                "port": typed_settings.port,
            }
        )


if __name__ == "__main__":
    raise SystemExit(main())
