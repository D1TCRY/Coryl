"""Layered config example."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from coryl import Coryl


with TemporaryDirectory() as temp_dir:
    root = Path(temp_dir)
    config_root = root / "config"
    config_root.mkdir(parents=True, exist_ok=True)
    (config_root / "defaults.toml").write_text(
        'debug = false\n[database]\nhost = "db"\n',
        encoding="utf-8",
    )
    (config_root / "local.toml").write_text(
        "[database]\nport = 5432\n",
        encoding="utf-8",
    )
    (config_root / ".secrets.toml").write_text(
        'token = "secret"\n',
        encoding="utf-8",
    )

    app = Coryl(root=root)
    settings = app.configs.layered(
        "settings",
        files=[
            "config/defaults.toml",
            "config/local.toml",
        ],
        env_prefix="MYAPP",
        secrets="config/.secrets.toml",
    )

    settings.apply_overrides(["database.host=localhost", "debug=true"])

    print(settings.as_dict()["debug"])
    print(settings.get("database.host"))
