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
    assert payload["cached_user"] == {"id": 42, "name": "Ada"}
    assert payload["debug"] is True
    assert payload["logo_name"] == "logo.svg"
    assert payload["profiles_count"] == 1


def _assert_cli_tool_config(payload: dict[str, object]) -> None:
    assert payload["created_default"] is True
    assert payload["session_state"] == "ready"
    assert payload["settings"] == {"retries": 2, "theme": "dark", "verbose": True}
    assert payload["typed"]["available"] is HAS_PYDANTIC_V2
    if HAS_PYDANTIC_V2:
        assert payload["typed"] == {
            "available": True,
            "retries": 2,
            "theme": "dark",
            "verbose": True,
        }


def _assert_api_cache(payload: dict[str, object]) -> None:
    assert payload["expired_value"] == "expired"
    assert payload["factory_calls"] == 2
    assert payload["first"] == {"etag": "v1", "id": 42}
    assert payload["second"] == {"etag": "v1", "id": 42}
    assert payload["third"] == {"etag": "v2", "id": 42}


def _assert_package_assets(payload: dict[str, object]) -> None:
    assert payload["matched_files"] == ["email.html"]
    assert payload["materialized_name"] == "email.html"
    assert payload["template_text"] == "<html>Hello from Coryl</html>"


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


def _assert_layered_config(payload: dict[str, object]) -> None:
    assert payload["database_host"] == "localhost"
    assert payload["debug"] is True
    assert payload["merged"] == {
        "database": {"host": "localhost", "port": 5432},
        "debug": True,
        "token": "secret",
    }


def _assert_desktop_app_assets(payload: dict[str, object]) -> None:
    assert payload["local_logo_name"] == "app.svg"
    assert payload["local_logo_text"] == "<svg>app</svg>"
    assert payload["package_files"] == ["templates/welcome.html"]
    assert payload["package_template"] == "<html>Welcome</html>"


def _assert_declarative_manifest(payload: dict[str, object]) -> None:
    assert payload["audit_safe"] == {
        "http_cache": True,
        "settings": True,
        "ui": True,
    }
    assert payload["cached_user"] == {"id": 42}
    assert payload["resource_names"] == ["http_cache", "settings", "ui"]
    assert payload["theme"] == "dark"
    assert payload["ui_exists"] is True


def _assert_installed_app(payload: dict[str, object]) -> None:
    assert payload["calls"] == [
        {
            "appauthor": "Acme",
            "appname": "demo",
            "ensure_exists": True,
            "multipath": True,
            "roaming": True,
            "version": "1.2.3",
        }
    ]
    assert payload["resource_parents"] == {
        "cache": "platform-cache",
        "data": "platform-data",
        "log": "platform-log",
        "settings": "platform-config",
    }
    assert payload["safe"] == {
        "http": True,
        "main": True,
        "settings": True,
        "state": True,
    }


def _assert_container_config(payload: dict[str, object]) -> None:
    assert payload["asset_text"] == "<svg>mounted</svg>"
    assert payload["base_config"] == {"debug": False, "region": "eu-west-1"}
    assert "read-only" in payload["blocked_write"]
    assert payload["merged_config"] == {
        "api_token": "top-secret",
        "debug": False,
        "region": "eu-west-1",
    }
    assert payload["readonly"] == {"assets": True, "settings": True}


def _assert_diskcache_optional(payload: dict[str, object]) -> None:
    assert payload["available"] is HAS_DISKCACHE
    if not HAS_DISKCACHE:
        assert payload["skipped"] is True
        assert payload["reason"] == "diskcache is not installed."
        return

    assert payload["cached_user"] == {"id": 42, "name": "Ada"}
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
    assert payload["root"].startswith("/")
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
    "cli_tool_config.py": _assert_cli_tool_config,
    "container_config.py": _assert_container_config,
    "declarative_manifest.py": _assert_declarative_manifest,
    "desktop_app_assets.py": _assert_desktop_app_assets,
    "diagnostics_cli.py": _assert_diagnostics_cli,
    "diskcache_optional.py": _assert_diskcache_optional,
    "fsspec_memory.py": _assert_fsspec_memory,
    "installed_app.py": _assert_installed_app,
    "layered_config.py": _assert_layered_config,
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
