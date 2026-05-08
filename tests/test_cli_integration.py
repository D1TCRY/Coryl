from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"


def _write_standard_manifest(root: Path) -> None:
    (root / "app.toml").write_text(
        """
version = 2

[resources.settings]
path = "config/settings.toml"
kind = "file"
role = "config"
create = false

[resources.http_cache]
path = ".cache/http"
kind = "directory"
role = "cache"
create = false

[resources.ui]
path = "assets/ui"
kind = "directory"
role = "assets"
create = false
""".strip()
        + "\n",
        encoding="utf-8",
    )


def _prepare_standard_root(root: Path) -> None:
    _write_standard_manifest(root)
    settings_path = root / "config" / "settings.toml"
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(
        'theme = "dark"\n[database]\nhost = "localhost"\nport = 5432\n',
        encoding="utf-8",
    )
    cache_file = root / ".cache" / "http" / "users" / "42.json"
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache_file.write_text('{"id": 42}\n', encoding="utf-8")
    asset_file = root / "assets" / "ui" / "logo.svg"
    asset_file.parent.mkdir(parents=True, exist_ok=True)
    asset_file.write_text("<svg></svg>\n", encoding="utf-8")


def _write_diskcache_manifest(root: Path) -> None:
    (root / "app.toml").write_text(
        """
version = 2

[resources.settings]
path = "config/settings.toml"
kind = "file"
role = "config"
create = false

[resources.http_cache]
path = ".cache/http"
kind = "directory"
role = "cache"
backend = "diskcache"
create = false
""".strip()
        + "\n",
        encoding="utf-8",
    )
    settings_path = root / "config" / "settings.toml"
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text('theme = "dark"\n', encoding="utf-8")


def _run_cli(
    root: Path,
    *args: str,
    blocked: tuple[str, ...] = (),
    modules: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    temp_modules: tempfile.TemporaryDirectory[str] | None = None
    try:
        pythonpath_parts = [str(SRC_ROOT)]
        if modules:
            temp_modules = tempfile.TemporaryDirectory()
            module_root = Path(temp_modules.name)
            for relative_path, content in modules.items():
                destination = module_root / relative_path
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_text(
                    textwrap.dedent(content).lstrip(), encoding="utf-8"
                )
            pythonpath_parts.insert(0, str(module_root))

        existing_pythonpath = os.environ.get("PYTHONPATH")
        if existing_pythonpath:
            pythonpath_parts.append(existing_pythonpath)

        env = os.environ.copy()
        env["PYTHONPATH"] = os.pathsep.join(pythonpath_parts)

        bootstrap = textwrap.dedent(
            f"""
            import builtins
            import importlib.abc
            import sys

            blocked = {set(blocked)!r}
            real_import = builtins.__import__

            for module_name in tuple(sys.modules):
                if module_name.split(".", 1)[0] in blocked:
                    sys.modules.pop(module_name, None)

            class BlockedModuleFinder(importlib.abc.MetaPathFinder):
                def find_spec(self, fullname, path=None, target=None):
                    if fullname.split(".", 1)[0] in blocked:
                        raise ModuleNotFoundError(f"No module named {{fullname!r}}")
                    return None

            sys.meta_path.insert(0, BlockedModuleFinder())

            def blocked_import(name, globals=None, locals=None, fromlist=(), level=0):
                if name.split(".", 1)[0] in blocked:
                    raise ModuleNotFoundError(f"No module named {{name!r}}")
                return real_import(name, globals, locals, fromlist, level)

            builtins.__import__ = blocked_import
            """
        )
        command = (
            bootstrap
            + "\n"
            + textwrap.dedent(
                f"""
            from coryl.cli import main

            raise SystemExit(main({list(args)!r}))
            """
            )
        )
        return subprocess.run(
            [sys.executable, "-c", command],
            capture_output=True,
            check=False,
            cwd=root,
            env=env,
            text=True,
        )
    finally:
        if temp_modules is not None:
            temp_modules.cleanup()


def test_cli_subcommands_work_with_manifest_and_root_flags(tmp_path: Path) -> None:
    _prepare_standard_root(tmp_path)

    listed = _run_cli(
        tmp_path, "resources", "list", "--manifest", "app.toml", "--root", "."
    )
    assert listed.returncode == 0
    assert listed.stderr == ""
    list_lines = listed.stdout.strip().splitlines()
    assert list_lines[0].split() == ["name", "role", "kind", "exists", "safe", "path"]
    assert [line.split()[0] for line in list_lines[2:]] == [
        "http_cache",
        "settings",
        "ui",
    ]

    checked = _run_cli(
        tmp_path, "resources", "check", "--manifest", "app.toml", "--root", "."
    )
    assert checked.returncode == 0
    assert checked.stderr == ""
    assert (
        checked.stdout.strip().splitlines()[-1] == "All resources are present and safe."
    )

    shown = _run_cli(
        tmp_path,
        "config",
        "show",
        "settings",
        "--manifest",
        "app.toml",
        "--root",
        ".",
    )
    assert shown.returncode == 0
    assert shown.stderr == ""
    assert "theme" in shown.stdout
    assert "dark" in shown.stdout
    assert "database" in shown.stdout

    cleared = _run_cli(
        tmp_path,
        "cache",
        "clear",
        "http_cache",
        "--manifest",
        "app.toml",
        "--root",
        ".",
    )
    assert cleared.returncode == 0
    assert cleared.stderr == ""
    assert "http_cache" in cleared.stdout
    assert list((tmp_path / ".cache" / "http").iterdir()) == []

    assets = _run_cli(
        tmp_path,
        "assets",
        "list",
        "ui",
        "--manifest",
        "app.toml",
        "--root",
        ".",
    )
    assert assets.returncode == 0
    assert assets.stderr == ""
    assert "logo.svg" in assets.stdout


def test_cli_json_output_is_valid_for_every_command(tmp_path: Path) -> None:
    _prepare_standard_root(tmp_path)

    commands = [
        ("resources", "list", "--manifest", "app.toml", "--root", ".", "--json"),
        ("resources", "check", "--manifest", "app.toml", "--root", ".", "--json"),
        (
            "config",
            "show",
            "settings",
            "--manifest",
            "app.toml",
            "--root",
            ".",
            "--json",
        ),
        (
            "cache",
            "clear",
            "http_cache",
            "--manifest",
            "app.toml",
            "--root",
            ".",
            "--json",
        ),
        ("assets", "list", "ui", "--manifest", "app.toml", "--root", ".", "--json"),
    ]

    for command in commands:
        result = _run_cli(tmp_path, *command)
        assert result.returncode == 0, result.stderr
        payload = json.loads(result.stdout)
        assert payload


def test_cli_reports_missing_resources_with_non_zero_exit(tmp_path: Path) -> None:
    _prepare_standard_root(tmp_path)

    for command in (
        ("config", "show", "missing", "--manifest", "app.toml", "--root", "."),
        ("cache", "clear", "missing", "--manifest", "app.toml", "--root", "."),
        ("assets", "list", "missing", "--manifest", "app.toml", "--root", "."),
    ):
        result = _run_cli(tmp_path, *command)
        assert result.returncode == 1
        assert result.stdout == ""
        assert result.stderr.startswith("Error: ")


def test_cli_reports_unsafe_manifest_with_non_zero_exit(tmp_path: Path) -> None:
    (tmp_path / "app.toml").write_text(
        """
version = 2

[resources.settings]
path = "config/../settings.toml"
kind = "file"
role = "config"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    result = _run_cli(
        tmp_path, "resources", "list", "--manifest", "app.toml", "--root", "."
    )

    assert result.returncode == 1
    assert result.stdout == ""
    assert "Path traversal is not allowed" in result.stderr


def test_cli_resources_commands_do_not_require_diskcache_dependency_for_manifest_inspection(
    tmp_path: Path,
) -> None:
    _write_diskcache_manifest(tmp_path)

    listed = _run_cli(
        tmp_path,
        "resources",
        "list",
        "--manifest",
        "app.toml",
        "--root",
        ".",
        "--json",
        blocked=("diskcache",),
    )
    assert listed.returncode == 0, listed.stderr
    payload = json.loads(listed.stdout)
    assert [resource["name"] for resource in payload["resources"]] == [
        "http_cache",
        "settings",
    ]

    shown = _run_cli(
        tmp_path,
        "config",
        "show",
        "settings",
        "--manifest",
        "app.toml",
        "--root",
        ".",
        "--json",
        blocked=("diskcache",),
    )
    assert shown.returncode == 0, shown.stderr
    assert json.loads(shown.stdout)["config"]["theme"] == "dark"


def test_cli_cache_clear_requires_diskcache_when_backend_is_selected(
    tmp_path: Path,
) -> None:
    _write_diskcache_manifest(tmp_path)

    result = _run_cli(
        tmp_path,
        "cache",
        "clear",
        "http_cache",
        "--manifest",
        "app.toml",
        "--root",
        ".",
        blocked=("diskcache",),
    )

    assert result.returncode == 1
    assert result.stdout == ""
    assert "Install coryl[diskcache] to use the diskcache backend." in result.stderr
