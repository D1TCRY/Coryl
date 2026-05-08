from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import textwrap
import tomllib
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest

from coryl import Coryl

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PYPROJECT_PATH = PROJECT_ROOT / "pyproject.toml"
SRC_ROOT = PROJECT_ROOT / "src"
OPTIONAL_MODULES = (
    "platformdirs",
    "pydantic",
    "diskcache",
    "fsspec",
    "watchfiles",
    "filelock",
)


def _run_python(
    code: str,
    *,
    blocked: tuple[str, ...] = (),
) -> subprocess.CompletedProcess[str]:
    existing_pythonpath = os.environ.get("PYTHONPATH")
    pythonpath_parts = [str(SRC_ROOT)]
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
    completed = subprocess.run(
        [sys.executable, "-c", bootstrap + "\n" + textwrap.dedent(code)],
        capture_output=True,
        check=False,
        env=env,
        text=True,
    )
    if completed.returncode != 0:
        pytest.fail(
            "Subprocess failed.\n"
            f"stdout:\n{completed.stdout}\n"
            f"stderr:\n{completed.stderr}"
        )
    return completed


def _make_fake_platformdirs_module(
    platform_roots: dict[str, Path],
) -> tuple[SimpleNamespace, list[dict[str, object]]]:
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

    return SimpleNamespace(PlatformDirs=FakePlatformDirs), calls


def test_pyproject_declares_packaging_metadata_for_core_and_optional_features() -> None:
    pyproject = tomllib.loads(PYPROJECT_PATH.read_text(encoding="utf-8"))
    project = pyproject["project"]
    optional = project["optional-dependencies"]
    setuptools_config = pyproject["tool"]["setuptools"]

    assert project["requires-python"] == ">=3.10"
    assert project["scripts"]["coryl"] == "coryl.cli:main"
    assert set(optional) >= {
        "cli",
        "lock",
        "diskcache",
        "fsspec",
        "platform",
        "pydantic",
        "watch",
        "yaml",
        "all",
    }
    assert optional["cli"] == []
    assert set(optional["all"]) >= set().union(
        optional["platform"],
        optional["pydantic"],
        optional["diskcache"],
        optional["fsspec"],
        optional["lock"],
        optional["watch"],
        optional["yaml"],
    )
    assert setuptools_config["include-package-data"] is True
    assert setuptools_config["package-data"]["coryl"] == ["py.typed"]
    assert (SRC_ROOT / "coryl" / "py.typed").is_file()
    assert project["license"] == "MIT"
    assert project["license-files"] == ["LICEN[CS]E*"]

    classifiers = set(project["classifiers"])
    assert {
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3 :: Only",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "Operating System :: OS Independent",
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Typing :: Typed",
    } <= classifiers


def test_import_coryl_keeps_optional_dependencies_unloaded() -> None:
    result = _run_python(
        """
        import json
        import sys

        import coryl

        loaded = {
            name: name in sys.modules
            for name in (
                "platformdirs",
                "pydantic",
                "diskcache",
                "fsspec",
                "watchfiles",
                "filelock",
            )
        }
        assert all(not is_loaded for is_loaded in loaded.values())
        print(json.dumps(loaded, sort_keys=True))
        """,
        blocked=OPTIONAL_MODULES,
    )

    assert result.stdout.strip() == (
        '{"diskcache": false, "filelock": false, "fsspec": false, '
        '"platformdirs": false, "pydantic": false, "watchfiles": false}'
    )


def test_core_flow_works_with_optional_dependencies_blocked() -> None:
    result = _run_python(
        """
        import json
        import tempfile

        from coryl import Coryl

        with tempfile.TemporaryDirectory() as temp_dir:
            app = Coryl(temp_dir)
            settings = app.configs.add("settings", "config/settings.toml")
            settings.save({"name": "core-only", "debug": True})
            print(json.dumps(settings.load(), sort_keys=True))
        """,
        blocked=OPTIONAL_MODULES,
    )

    assert result.stdout.strip() == '{"debug": true, "name": "core-only"}'


@pytest.mark.parametrize(
    ("blocked_module", "script", "expected_message"),
    [
        (
            "filelock",
            """
            import tempfile

            from coryl import Coryl, CorylOptionalDependencyError

            with tempfile.TemporaryDirectory() as temp_dir:
                app = Coryl(temp_dir)
                notes = app.register_file("notes", "notes.txt")
                try:
                    with notes.lock():
                        raise AssertionError("lock context should not be entered")
                except CorylOptionalDependencyError as error:
                    print(str(error))
                else:
                    raise AssertionError("Expected the filelock dependency error.")
            """,
            "Resource locking requires the optional 'filelock' dependency. "
            "Install it with 'pip install coryl[lock]'.",
        ),
        (
            "platformdirs",
            """
            from coryl import Coryl, CorylOptionalDependencyError

            try:
                Coryl.for_app("demo")
            except CorylOptionalDependencyError as error:
                print(str(error))
            else:
                raise AssertionError("Expected the platformdirs dependency error.")
            """,
            "Coryl.for_app() requires the optional 'platformdirs' dependency. "
            "Install it with 'pip install coryl[platform]'.",
        ),
        (
            "pydantic",
            """
            import tempfile

            from coryl import Coryl, CorylOptionalDependencyError

            class Settings:
                @classmethod
                def model_validate(cls, data):
                    return cls()

            with tempfile.TemporaryDirectory() as temp_dir:
                app = Coryl(temp_dir)
                settings = app.configs.add("settings", "config/settings.toml", schema=Settings)
                settings.save({"host": "localhost", "port": 5432})
                try:
                    settings.load_typed()
                except CorylOptionalDependencyError as error:
                    print(str(error))
                else:
                    raise AssertionError("Expected the pydantic dependency error.")
            """,
            "Typed config helpers require the optional 'pydantic' dependencies. "
            "Install them with 'pip install coryl[pydantic]'.",
        ),
        (
            "diskcache",
            """
            import tempfile

            from coryl import Coryl, CorylOptionalDependencyError

            with tempfile.TemporaryDirectory() as temp_dir:
                app = Coryl(temp_dir)
                try:
                    app.caches.add("api", "cache/api", backend="diskcache")
                except CorylOptionalDependencyError as error:
                    print(str(error))
                else:
                    raise AssertionError("Expected the diskcache dependency error.")
            """,
            "Install coryl[diskcache] to use the diskcache backend.",
        ),
        (
            "watchfiles",
            """
            import tempfile

            from coryl import Coryl, CorylOptionalDependencyError

            with tempfile.TemporaryDirectory() as temp_dir:
                app = Coryl(temp_dir)
                settings = app.configs.add("settings", "config/settings.json")
                settings.save({"theme": "light"})
                try:
                    next(settings.watch_reload())
                except CorylOptionalDependencyError as error:
                    print(str(error))
                else:
                    raise AssertionError("Expected the watchfiles dependency error.")
            """,
            "File watching requires the optional 'watchfiles' dependency. "
            "Install it with 'pip install coryl[watch]'.",
        ),
        (
            "fsspec",
            """
            from coryl import Coryl, CorylOptionalDependencyError

            try:
                Coryl.with_fs("memory://demo")
            except CorylOptionalDependencyError as error:
                print(str(error))
            else:
                raise AssertionError("Expected the fsspec dependency error.")
            """,
            "Optional fsspec filesystem support requires the 'fsspec' dependency. "
            "Install it with 'pip install coryl[fsspec]'.",
        ),
    ],
    ids=("lock", "platform", "pydantic", "diskcache", "watch", "fsspec"),
)
def test_missing_optional_dependency_error_messages_are_actionable(
    blocked_module: str,
    script: str,
    expected_message: str,
) -> None:
    result = _run_python(script, blocked=(blocked_module,))
    assert result.stdout.strip() == expected_message


def test_for_app_routes_named_roots_and_keeps_assets_under_the_data_root(
    tmp_path: Path,
) -> None:
    platform_roots = {
        "config": tmp_path / "config",
        "cache": tmp_path / "cache",
        "data": tmp_path / "data",
        "log": tmp_path / "log",
    }
    fake_platformdirs, calls = _make_fake_platformdirs_module(platform_roots)

    with mock.patch("coryl.manager.import_module", return_value=fake_platformdirs):
        app = Coryl.for_app(
            "demo",
            app_author="Acme",
            version="1.2.3",
            ensure=True,
            create_missing=False,
        )

    assert calls == [
        {
            "appname": "demo",
            "appauthor": "Acme",
            "version": "1.2.3",
            "roaming": False,
            "multipath": False,
            "ensure_exists": True,
        }
    ]
    assert app.root_path == platform_roots["data"].resolve()
    assert app.config_root_path == platform_roots["config"].resolve()
    assert app.cache_root_path == platform_roots["cache"].resolve()
    assert app.data_root_path == platform_roots["data"].resolve()
    assert app.log_root_path == platform_roots["log"].resolve()
    for path in platform_roots.values():
        assert path.is_dir()

    settings = app.configs.add("settings", "settings.toml")
    cache = app.caches.add("http", "http")
    data = app.data.add("state", "state.json")
    logs = app.logs.add("main", "app.log")
    assets = app.assets.add("ui", "assets/ui")

    assert settings.path == (platform_roots["config"] / "settings.toml").resolve()
    assert cache.path == (platform_roots["cache"] / "http").resolve()
    assert data.path == (platform_roots["data"] / "state.json").resolve()
    assert logs.path == (platform_roots["log"] / "app.log").resolve()
    assert assets.path == (platform_roots["data"] / "assets" / "ui").resolve()

    assert settings.exists() is False
    assert cache.exists() is False
    assert data.exists() is False
    assert logs.exists() is False
    assert assets.exists() is False


def test_for_app_ensure_false_defers_root_creation_to_resource_creation(
    tmp_path: Path,
) -> None:
    platform_roots = {
        "config": tmp_path / "config",
        "cache": tmp_path / "cache",
        "data": tmp_path / "data",
        "log": tmp_path / "log",
    }
    fake_platformdirs, calls = _make_fake_platformdirs_module(platform_roots)

    with mock.patch("coryl.manager.import_module", return_value=fake_platformdirs):
        app = Coryl.for_app("demo", ensure=False, create_missing=True)

    assert calls[0]["ensure_exists"] is False
    for path in platform_roots.values():
        assert path.exists() is False

    settings = app.configs.add("settings", "settings.toml")
    assets = app.assets.add("ui", "assets/ui")

    assert settings.exists() is True
    assert assets.exists() is True
    assert platform_roots["config"].is_dir()
    assert platform_roots["data"].is_dir()
    assert platform_roots["cache"].exists() is False
    assert platform_roots["log"].exists() is False
