from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"

FAKE_YAML_MODULE = """
class SafeLoader:
    constructors = {}

    @classmethod
    def add_constructor(cls, tag, constructor):
        cls.constructors[tag] = constructor


class nodes:
    class MappingNode:
        def __init__(self, value=None):
            self.value = value or []


class resolver:
    class BaseResolver:
        DEFAULT_MAPPING_TAG = "tag:yaml.org,2002:map"


def _parse_scalar(raw_value):
    value = raw_value.strip()
    lowered = value.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if value.isdigit():
        return int(value)
    if value.startswith(("'", '"')) and value.endswith(("'", '"')):
        return value[1:-1]
    return value


def safe_load(text):
    if not text.strip():
        return None
    payload = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        key, _, value = line.partition(":")
        payload[key.strip()] = _parse_scalar(value)
    return payload


def load(text, Loader=None):
    return safe_load(text)


def safe_dump(content, allow_unicode=True, sort_keys=False):
    items = sorted(content.items()) if sort_keys else content.items()
    return "".join(f"{key}: {str(value).lower() if isinstance(value, bool) else value}\\n" for key, value in items)
"""

FAKE_PYDANTIC_MODULE = """
class ValidationError(Exception):
    pass


class BaseModel:
    @classmethod
    def model_validate(cls, data):
        if not isinstance(data, dict):
            raise ValidationError("Input should be a mapping.")
        return cls(**data)

    def model_dump(self, *, mode="json"):
        if mode != "json":
            raise AssertionError(f"Unexpected dump mode: {mode!r}")
        return dict(self.__dict__)
"""

FAKE_PLATFORMDIRS_MODULE = """
import os
from pathlib import Path


class PlatformDirs:
    def __init__(
        self,
        *,
        appname=None,
        appauthor=None,
        version=None,
        roaming=False,
        multipath=False,
        ensure_exists=False,
    ):
        del appname, appauthor, version, roaming, multipath
        root = Path(os.environ["CORYL_PLATFORM_ROOT"]).resolve()
        self.user_config_path = root / "config"
        self.user_cache_path = root / "cache"
        self.user_data_path = root / "data"
        self.user_log_path = root / "log"
        if ensure_exists:
            for path in (
                self.user_config_path,
                self.user_cache_path,
                self.user_data_path,
                self.user_log_path,
            ):
                path.mkdir(parents=True, exist_ok=True)
"""

FAKE_DISKCACHE_MODULE = """
from pathlib import Path


class Cache:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self._entries = {}

    def set(self, key, value, expire=None):
        del expire
        self._entries[key] = value
        return True

    def get(self, key, default=None):
        return self._entries.get(key, default)

    def delete(self, key):
        return self._entries.pop(key, None) is not None

    def clear(self):
        removed = len(self._entries)
        self._entries.clear()
        return removed

    def expire(self):
        return 0

    def memoize(self, *, expire=None):
        del expire

        def decorator(function):
            def wrapper(*args, **kwargs):
                key = (function.__qualname__, args, tuple(sorted(kwargs.items())))
                if key in self._entries:
                    return self._entries[key]
                value = function(*args, **kwargs)
                self._entries[key] = value
                return value

            return wrapper

        return decorator

    def close(self):
        return None

    def __contains__(self, key):
        return key in self._entries
"""


class DependencyMatrixTests(unittest.TestCase):
    def test_core_only_default_flow_stays_available(self) -> None:
        self._run_case(
            """
            import os
            import sys
            import tempfile

            import coryl

            assert "coryl.manager" not in sys.modules
            assert "coryl.resources" not in sys.modules
            assert "coryl.serialization" not in sys.modules

            with tempfile.TemporaryDirectory() as temp_dir:
                previous_cwd = os.getcwd()
                os.chdir(temp_dir)
                try:
                    app = coryl.Coryl(root=".")
                    settings = app.configs.add("settings", "config/settings.toml")
                    assert settings.load() == {}
                    settings.save({"name": "core-only", "debug": True})
                    assert settings.load()["name"] == "core-only"
                finally:
                    os.chdir(previous_cwd)
            """,
            blocked=("yaml", "pydantic", "platformdirs", "diskcache", "watchfiles", "fsspec", "filelock"),
        )

    def test_yaml_extra_can_be_used_without_other_optionals(self) -> None:
        self._run_case(
            """
            import os
            import tempfile

            from coryl import Coryl

            with tempfile.TemporaryDirectory() as temp_dir:
                previous_cwd = os.getcwd()
                os.chdir(temp_dir)
                try:
                    app = Coryl(root=".")
                    settings = app.configs.add("settings", "config/settings.yaml")
                    settings.save({"theme": "dark", "debug": True})
                    assert settings.load() == {"theme": "dark", "debug": True}
                finally:
                    os.chdir(previous_cwd)
            """,
            blocked=("pydantic", "platformdirs", "diskcache", "watchfiles", "fsspec", "filelock"),
            modules={"yaml.py": FAKE_YAML_MODULE},
        )

    def test_yaml_error_is_clear_when_extra_is_missing(self) -> None:
        self._run_case(
            """
            import os
            import tempfile

            from coryl import Coryl, CorylOptionalDependencyError

            with tempfile.TemporaryDirectory() as temp_dir:
                previous_cwd = os.getcwd()
                os.chdir(temp_dir)
                try:
                    app = Coryl(root=".")
                    settings = app.configs.add("settings", "config/settings.yaml")
                    try:
                        settings.save({"theme": "dark"})
                    except CorylOptionalDependencyError as error:
                        assert "pip install coryl[yaml]" in str(error)
                    else:
                        raise AssertionError("Expected a YAML optional dependency error.")
                finally:
                    os.chdir(previous_cwd)
            """,
            blocked=("yaml", "pydantic", "platformdirs", "diskcache", "watchfiles", "fsspec", "filelock"),
        )

    def test_pydantic_extra_can_be_used_without_other_optionals(self) -> None:
        self._run_case(
            """
            import tempfile

            from coryl import Coryl
            from pydantic import BaseModel

            class Settings(BaseModel):
                def __init__(self, host: str, port: int, debug: bool = False) -> None:
                    self.host = host
                    self.port = port
                    self.debug = debug

            with tempfile.TemporaryDirectory() as temp_dir:
                app = Coryl(temp_dir)
                settings = app.configs.add("settings", "config/settings.toml", schema=Settings)
                settings.save({"host": "localhost", "port": 5432, "debug": True})
                typed = settings.load_typed()
                assert typed.port == 5432
                settings.save_typed(typed)
                assert settings.load()["debug"] is True
            """,
            blocked=("yaml", "platformdirs", "diskcache", "watchfiles", "fsspec", "filelock"),
            modules={"pydantic.py": FAKE_PYDANTIC_MODULE},
        )

    def test_platform_extra_can_be_used_without_other_optionals(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            self._run_case(
                """
                from pathlib import Path

                from coryl import Coryl

                root = Path(__import__("os").environ["CORYL_PLATFORM_ROOT"]).resolve()
                app = Coryl.for_app("mytool", ensure=True)
                settings = app.configs.add("settings", "settings.toml")
                cache = app.caches.add("http", "http")

                assert settings.path == (root / "config" / "settings.toml").resolve()
                assert cache.path == (root / "cache" / "http").resolve()
                """,
                blocked=("yaml", "pydantic", "diskcache", "watchfiles", "fsspec", "filelock"),
                modules={"platformdirs.py": FAKE_PLATFORMDIRS_MODULE},
                env_updates={"CORYL_PLATFORM_ROOT": temp_dir},
            )

    def test_diskcache_extra_can_be_used_without_other_optionals(self) -> None:
        self._run_case(
            """
            import tempfile

            from coryl import Coryl

            with tempfile.TemporaryDirectory() as temp_dir:
                app = Coryl(temp_dir)
                cache = app.caches.diskcache("api", ".cache/api")
                cache.set("users:42", {"id": 42}, ttl=60)
                assert cache.get("users:42")["id"] == 42
                assert cache.remember_json("users/7.json", lambda: {"id": 7})["id"] == 7
            """,
            blocked=("yaml", "pydantic", "platformdirs", "watchfiles", "fsspec", "filelock"),
            modules={"diskcache.py": FAKE_DISKCACHE_MODULE},
        )

    def _run_case(
        self,
        script: str,
        *,
        blocked: tuple[str, ...] = (),
        modules: dict[str, str] | None = None,
        env_updates: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as module_dir:
            module_root = Path(module_dir)
            for relative_path, content in (modules or {}).items():
                destination = module_root / relative_path
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_text(textwrap.dedent(content).lstrip(), encoding="utf-8")

            pythonpath_parts = [str(module_root), str(SRC_ROOT)]
            existing_pythonpath = os.environ.get("PYTHONPATH")
            if existing_pythonpath:
                pythonpath_parts.append(existing_pythonpath)

            env = os.environ.copy()
            env["PYTHONPATH"] = os.pathsep.join(pythonpath_parts)
            if env_updates:
                env.update(env_updates)

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
            code = bootstrap + "\n" + textwrap.dedent(script)
            completed = subprocess.run(
                [sys.executable, "-c", code],
                capture_output=True,
                check=False,
                env=env,
                text=True,
            )
            if completed.returncode != 0:
                self.fail(
                    "Dependency matrix case failed.\n"
                    f"stdout:\n{completed.stdout}\n"
                    f"stderr:\n{completed.stderr}"
                )
            return completed


if __name__ == "__main__":
    unittest.main()
