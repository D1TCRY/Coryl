"""Installed app example using ``Coryl.for_app`` with mocked platformdirs."""

from __future__ import annotations

from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import mock

EXAMPLES_DIR = Path(__file__).resolve().parent if "__file__" in globals() else Path.cwd() / "examples"
if str(EXAMPLES_DIR) not in sys.path:
    sys.path.insert(0, str(EXAMPLES_DIR))

from _support import emit_json, ensure_src_path

ensure_src_path()

from coryl import Coryl


def main() -> int:
    with TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        platform_roots = {
            "config": root / "platform-config",
            "cache": root / "platform-cache",
            "data": root / "platform-data",
            "log": root / "platform-log",
        }
        calls: list[dict[str, object]] = []

        class FakePlatformDirs:
            def __init__(
                self,
                *,
                appname: str | None = None,
                appauthor: str | None = None,
                version: str | None = None,
                roaming: bool = False,
                multipath: bool = False,
                ensure_exists: bool = False,
            ) -> None:
                calls.append(
                    {
                        "appname": appname,
                        "appauthor": appauthor,
                        "version": version,
                        "roaming": roaming,
                        "multipath": multipath,
                        "ensure_exists": ensure_exists,
                    }
                )
                self.user_config_path = platform_roots["config"]
                self.user_cache_path = platform_roots["cache"]
                self.user_data_path = platform_roots["data"]
                self.user_log_path = platform_roots["log"]
                if ensure_exists:
                    for path in platform_roots.values():
                        path.mkdir(parents=True, exist_ok=True)

        with mock.patch(
            "coryl.manager.import_module",
            return_value=SimpleNamespace(PlatformDirs=FakePlatformDirs),
        ):
            app = Coryl.for_app(
                "demo",
                app_author="Acme",
                version="1.2.3",
                roaming=True,
                multipath=True,
                ensure=True,
            )

        settings = app.configs.add("settings", "settings.toml")
        cache = app.caches.add("http", "http")
        data = app.data.add("state", "state.json")
        log = app.logs.add("main", "app.log")
        audit = app.audit_paths()

        return emit_json(
            {
                "calls": calls,
                "resource_parents": {
                    "cache": cache.path.parent.name,
                    "data": data.path.parent.name,
                    "log": log.path.parent.name,
                    "settings": settings.path.parent.name,
                },
                "safe": {
                    name: details["safe"]
                    for name, details in sorted(audit["resources"].items())
                },
            }
        )


if __name__ == "__main__":
    raise SystemExit(main())
