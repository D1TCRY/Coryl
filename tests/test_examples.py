from __future__ import annotations

import importlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import Callable

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXAMPLES_DIR = PROJECT_ROOT / "examples"


def _has_pydantic_v2() -> bool:
    if importlib.util.find_spec("pydantic") is None:
        return False

    pydantic = importlib.import_module("pydantic")
    return hasattr(pydantic.BaseModel, "model_validate")


HAS_PYDANTIC_V2 = _has_pydantic_v2()
HAS_DISKCACHE = importlib.util.find_spec("diskcache") is not None
HAS_FSSPEC = importlib.util.find_spec("fsspec") is not None


def _run_example(script_name: str) -> dict[str, object]:
    result = subprocess.run(
        [sys.executable, str(EXAMPLES_DIR / script_name)],
        capture_output=True,
        check=False,
        cwd=PROJECT_ROOT,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert result.stderr == ""
    return json.loads(result.stdout)


def _assert_simple_local_app(payload: dict[str, object]) -> None:
    assert payload["app_name"] == "Coryl Demo"
    assert payload["cached_user"] == {"id": 1, "name": "Ada"}
    assert payload["debug"] is True
    assert payload["locale"] == "en-US"
    assert payload["logo_name"] == "logo.svg"


def _assert_cli_tool_config(payload: dict[str, object]) -> None:
    assert payload["created_default"] is True
    assert payload["retries"] == 3
    assert payload["value"] == "dark"


def _assert_api_cache(payload: dict[str, object]) -> None:
    assert payload["factory_calls"] == 1
    assert payload["first"] == {"call": 1, "id": 42, "name": "Ada"}
    assert payload["second"] == {"call": 1, "id": 42, "name": "Ada"}


def _assert_package_assets(payload: dict[str, object]) -> None:
    assert payload["copied_files"] == ["icons/app.bin", "templates/welcome.txt"]
    assert payload["icon_size"] == 5
    assert payload["template_text"] == "Hello from package"


def _assert_typed_config(payload: dict[str, object]) -> None:
    assert payload["available"] is HAS_PYDANTIC_V2
    if HAS_PYDANTIC_V2:
        assert payload == {
            "available": True,
            "debug": True,
            "host": "localhost",
            "port": 5432,
        }
    else:
        assert "reason" in payload
        assert payload["skipped"] is True


def _assert_layered_config(payload: dict[str, object]) -> None:
    assert payload["database_host"] == "env-db"
    assert payload["debug"] is True
    assert payload["merged"] == {
        "database": {"host": "env-db", "port": 5432},
        "debug": True,
        "theme": "local",
    }


def _assert_desktop_app_assets(payload: dict[str, object]) -> None:
    assert payload["files"] == ["icons/app.ico", "templates/window.html"]
    assert payload["glob_matches"] == ["templates/window.html"]
    assert payload["icon_name"] == "app.ico"
    assert payload["template_text"] == "<main>Window</main>"


def _assert_manifest_startup(payload: dict[str, object]) -> None:
    audit = payload["audit_paths"]
    assert audit["resources"]["http_cache"]["safe"] is True
    assert audit["resources"]["settings"]["safe"] is True
    assert audit["resources"]["ui"]["safe"] is True
    assert payload["cached_user"] == {"id": 42}
    assert payload["logo_name"] == "logo.svg"
    assert payload["resource_names"] == ["http_cache", "settings", "ui"]
    assert payload["theme"] == "dark"


def _assert_cache_diskcache(payload: dict[str, object]) -> None:
    assert payload["available"] is HAS_DISKCACHE
    if not HAS_DISKCACHE:
        assert payload["skipped"] is True
        assert payload["reason"] == "diskcache is not installed."
        return

    assert payload["factory_calls"] == 1
    assert payload["first"] == {"call": 1, "id": 7}
    assert payload["second"] == {"call": 1, "id": 7}


def _assert_fsspec_memory(payload: dict[str, object]) -> None:
    assert payload["available"] is HAS_FSSPEC
    if not HAS_FSSPEC:
        assert payload["skipped"] is True
        assert payload["reason"] == "fsspec is not installed."
        return

    assert payload["factory_calls"] == 1
    assert payload["configured_root"].startswith("memory://")
    assert payload["first"] == {"call": 1, "id": 42}
    assert payload["logo_text"] == "logo"
    assert payload["second"] == {"call": 1, "id": 42}
    assert payload["settings"] == {"debug": True, "theme": "light"}


def _assert_diagnostics_cli(payload: dict[str, object]) -> None:
    assert payload["returncodes"] == {"check": 0, "list": 0, "show": 0}
    assert payload["resources_check"]["ok"] is True
    assert [
        resource["name"] for resource in payload["resources_list"]["resources"]
    ] == [
        "http_cache",
        "settings",
        "ui",
    ]
    assert payload["config_show"]["config"] == {
        "database": {"host": "localhost", "port": 5432},
        "theme": "dark",
    }


VALIDATORS: dict[str, Callable[[dict[str, object]], None]] = {
    "api_cache.py": _assert_api_cache,
    "cache_diskcache.py": _assert_cache_diskcache,
    "cli_tool_config.py": _assert_cli_tool_config,
    "desktop_app_assets.py": _assert_desktop_app_assets,
    "diagnostics_cli.py": _assert_diagnostics_cli,
    "fsspec_memory.py": _assert_fsspec_memory,
    "layered_config.py": _assert_layered_config,
    "manifest_startup.py": _assert_manifest_startup,
    "package_assets.py": _assert_package_assets,
    "simple_local_app.py": _assert_simple_local_app,
    "typed_config.py": _assert_typed_config,
}


def test_example_registry_matches_scripts() -> None:
    discovered = sorted(
        path.name for path in EXAMPLES_DIR.glob("*.py") if not path.name.startswith("_")
    )

    assert discovered == sorted(VALIDATORS)


@pytest.mark.parametrize("script_name", sorted(VALIDATORS), ids=sorted(VALIDATORS))
def test_examples_execute(script_name: str) -> None:
    payload = _run_example(script_name)
    VALIDATORS[script_name](payload)
