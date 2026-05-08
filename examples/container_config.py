"""Container-style readonly config and assets example."""

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

from _support import emit_json, ensure_src_path, write_block, write_text

ensure_src_path()

from coryl import Coryl, CorylReadOnlyResourceError


def main() -> int:
    with TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        write_block(
            root / "config" / "settings.toml",
            """
            debug = false
            region = "eu-west-1"
            """,
        )
        write_text(root / "run" / "secrets" / "api_token", "top-secret")
        write_text(
            root / "mounted" / "assets" / "ui" / "logo.svg", "<svg>mounted</svg>"
        )

        app = Coryl(root=root)
        settings = app.configs.layered(
            "settings",
            files=["config/settings.toml"],
            readonly=True,
            secrets_dir="run/secrets",
        )
        assets = app.assets.add("ui", "mounted/assets/ui", readonly=True)
        logo = assets.file("logo.svg")

        blocked_write = ""
        try:
            logo.write_text("<svg>updated</svg>")
        except CorylReadOnlyResourceError as error:
            blocked_write = str(error)

        return emit_json(
            {
                "asset_text": logo.read_text(),
                "base_config": settings.load_base(),
                "blocked_write": blocked_write,
                "merged_config": settings.as_dict(),
                "readonly": {
                    "assets": assets.readonly,
                    "settings": settings.readonly,
                },
            }
        )


if __name__ == "__main__":
    raise SystemExit(main())
