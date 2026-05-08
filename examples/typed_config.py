"""Typed config example.

Requires: pip install coryl[pydantic]
"""

from __future__ import annotations

from pathlib import Path
from pydantic import BaseModel
from tempfile import TemporaryDirectory

from coryl import Coryl


class SettingsModel(BaseModel):
    host: str
    port: int
    debug: bool = False


with TemporaryDirectory() as temp_dir:
    root = Path(temp_dir)
    app = Coryl(root=root)
    settings = app.configs.add("settings", "config/settings.toml", schema=SettingsModel)

    settings.save_typed(SettingsModel(host="localhost", port=5432, debug=True))

    typed_settings = settings.load_typed()
    print(typed_settings.port)
