from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
import textwrap
import tomllib
import unittest
from pathlib import Path
from typing import get_args

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
README_PATH = PROJECT_ROOT / "README.md"
PYPROJECT_PATH = PROJECT_ROOT / "pyproject.toml"
CHANGELOG_PATH = PROJECT_ROOT / "CHANGELOG.md"
MANIFEST_PATH = PROJECT_ROOT / "MANIFEST.in"
TOX_PATH = PROJECT_ROOT / "tox.ini"

FAKE_PYDANTIC_MODULE = """
class ValidationError(Exception):
    pass


class BaseModel:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

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


class ReleaseReadinessTests(unittest.TestCase):
    def test_pyproject_metadata_covers_release_requirements(self) -> None:
        pyproject = tomllib.loads(PYPROJECT_PATH.read_text(encoding="utf-8"))
        project = pyproject["project"]
        optional = project["optional-dependencies"]
        setuptools_config = pyproject["tool"]["setuptools"]

        self.assertEqual(project["version"], "0.0.2")
        self.assertEqual(project["requires-python"], ">=3.10")
        self.assertEqual(
            project["urls"],
            {"Home-Page": "https://github.com/D1TCRY/Coryl"},
        )
        self.assertIn("Programming Language :: Python :: 3.10", project["classifiers"])
        self.assertIn("Programming Language :: Python :: 3.11", project["classifiers"])
        self.assertIn("Programming Language :: Python :: 3.12", project["classifiers"])
        self.assertIn("Programming Language :: Python :: 3.13", project["classifiers"])
        self.assertIn("Typing :: Typed", project["classifiers"])
        self.assertEqual(project["license"], "MIT")
        self.assertEqual(project["license-files"], ["LICEN[CS]E*"])
        self.assertEqual(
            set(optional),
            {
                "platform",
                "pydantic",
                "diskcache",
                "watch",
                "fsspec",
                "lock",
                "cli",
                "yaml",
                "all",
            },
        )
        self.assertIn("PyYAML>=6.0", optional["yaml"])
        self.assertIn("platformdirs>=4", optional["all"])
        self.assertIn("pydantic>=2", optional["all"])
        self.assertIn("diskcache>=5", optional["all"])
        self.assertTrue(setuptools_config["include-package-data"])
        self.assertEqual(setuptools_config["package-data"]["coryl"], ["py.typed"])
        self.assertTrue((SRC_ROOT / "coryl" / "py.typed").is_file())

    def test_changelog_entry_exists_for_current_release(self) -> None:
        changelog = CHANGELOG_PATH.read_text(encoding="utf-8")

        self.assertIn("## 0.0.2 - 2026-05-08", changelog)
        self.assertEqual(changelog.count("## 0.0.2 - 2026-05-08"), 1)
        self.assertIn("Packaging metadata patch release", changelog)
        self.assertIn("GitHub repository as the package `Home-Page`", changelog)
        self.assertIn("packaging, documentation clarity, and reproducible QA", changelog)
        self.assertIn("First tagged public API baseline", changelog)
        self.assertIn("### Breaking changes", changelog)
        self.assertIn("### Migration notes", changelog)
        self.assertIn("### Optional extras", changelog)
        self.assertIn("### Known limitations", changelog)
        self.assertIn("MANIFEST.in", changelog)
        self.assertIn("YAML-backed fsspec tests", changelog)
        self.assertIn("Core safety checks", changelog)
        self.assertIn("Atomic writes", changelog)
        self.assertIn("diskcache", changelog)
        self.assertIn("fsspec", changelog)
        self.assertIn("CLI", changelog)

    def test_quality_tooling_and_manifest_policy_are_configured(self) -> None:
        pyproject = tomllib.loads(PYPROJECT_PATH.read_text(encoding="utf-8"))
        dependency_groups = pyproject["dependency-groups"]
        coverage_run = pyproject["tool"]["coverage"]["run"]
        coverage_report = pyproject["tool"]["coverage"]["report"]
        mypy_config = pyproject["tool"]["mypy"]
        ruff_config = pyproject["tool"]["ruff"]
        ruff_lint = ruff_config["lint"]

        self.assertIn("pytest>=8", dependency_groups["test"])
        self.assertIn("pytest-cov>=5", dependency_groups["test"])
        self.assertIn("mypy>=1.11,<2", dependency_groups["type"])
        self.assertIn("ruff>=0.11", dependency_groups["dev"])
        self.assertIn({"include-group": "test"}, dependency_groups["dev"])
        self.assertIn({"include-group": "type"}, dependency_groups["dev"])

        self.assertEqual(coverage_run["source"], ["coryl"])
        self.assertTrue(coverage_run["branch"])
        self.assertTrue(coverage_report["show_missing"])

        self.assertEqual(mypy_config["python_version"], "3.10")
        self.assertEqual(mypy_config["files"], ["src/coryl"])
        self.assertEqual(mypy_config["mypy_path"], ["src"])
        self.assertTrue(mypy_config["check_untyped_defs"])
        self.assertTrue(mypy_config["warn_unused_ignores"])
        self.assertTrue(mypy_config["show_error_codes"])
        self.assertTrue(mypy_config["ignore_missing_imports"])

        self.assertEqual(ruff_config["target-version"], "py310")
        self.assertEqual(ruff_config["line-length"], 88)
        self.assertEqual(ruff_config["src"], ["src", "tests", "examples"])
        self.assertEqual(ruff_config["extend-exclude"], ["tmp"])
        self.assertEqual(ruff_lint["select"], ["F"])

        manifest = MANIFEST_PATH.read_text(encoding="utf-8")
        self.assertIn("include README.md", manifest)
        self.assertIn("include LICENSE", manifest)
        self.assertIn("include CHANGELOG.md", manifest)
        self.assertIn("include AGENTS.md", manifest)
        self.assertIn("graft docs", manifest)
        self.assertIn("graft examples", manifest)
        self.assertIn("graft tests", manifest)
        self.assertIn("global-exclude *.py[cod]", manifest)

    def test_fsspec_tox_env_installs_yaml_extra_for_yaml_backed_tests(self) -> None:
        tox_ini = TOX_PATH.read_text(encoding="utf-8")
        match = re.search(
            r"^\[testenv:fsspec\]\s+extras =\s+(?P<extras>.*?)(?:^\[|\Z)",
            tox_ini,
            flags=re.MULTILINE | re.DOTALL,
        )
        self.assertIsNotNone(match)
        extras = match.group("extras")
        self.assertIn("fsspec", extras)
        self.assertIn("yaml", extras)

    def test_public_package_exports_remain_available(self) -> None:
        import coryl

        expected_exports = {
            "Coryl",
            "ResourceManager",
            "ResourceSpec",
            "CorylError",
            "ManifestFormatError",
            "LayeredConfigResource",
        }

        self.assertTrue(expected_exports.issubset(set(coryl.__all__)))
        for name in expected_exports:
            self.assertTrue(hasattr(coryl, name), name)
            self.assertIn(name, dir(coryl))

    def test_public_namespaces_and_resource_role_are_runtime_visible(self) -> None:
        import coryl

        namespace_exports = (
            "AssetNamespace",
            "CacheNamespace",
            "ConfigNamespace",
            "DataNamespace",
            "LogNamespace",
        )
        for name in namespace_exports:
            self.assertTrue(hasattr(coryl, name), name)

        self.assertEqual(
            get_args(coryl.ResourceRole),
            ("resource", "config", "cache", "assets", "data", "logs"),
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            app = coryl.Coryl(root=temp_dir)

            self.assertIsInstance(app.assets, coryl.AssetNamespace)
            self.assertIsInstance(app.caches, coryl.CacheNamespace)
            self.assertIsInstance(app.configs, coryl.ConfigNamespace)
            self.assertIsInstance(app.data, coryl.DataNamespace)
            self.assertIsInstance(app.logs, coryl.LogNamespace)

            data = app.data.add("state", "data/state.json")
            log = app.logs.add("main", "logs/app.log")

            self.assertEqual(data.role, "data")
            self.assertEqual(log.role, "logs")

    def test_public_conflict_and_missing_resource_errors_are_raised(self) -> None:
        import coryl

        with tempfile.TemporaryDirectory() as temp_dir:
            app = coryl.Coryl(root=temp_dir)
            app.configs.add("settings", "config/settings.toml")

            with self.assertRaises(coryl.ResourceConflictError):
                app.configs.add("settings", "config/settings.toml")

            with self.assertRaises(coryl.CorylResourceNotFoundError):
                app.resource("missing")

    def test_importing_coryl_stays_lightweight(self) -> None:
        result = self._run_python(
            """
            import json
            import sys

            import coryl

            loaded = set(sys.modules)
            optional = sorted(
                loaded.intersection(
                    {
                        "yaml",
                        "pydantic",
                        "platformdirs",
                        "diskcache",
                        "watchfiles",
                        "fsspec",
                        "filelock",
                    }
                )
            )
            core = sorted(
                name
                for name in ("coryl.manager", "coryl.resources", "coryl.serialization")
                if name in loaded
            )
            print(json.dumps({"optional": optional, "core": core}))
            """
        )
        self.assertEqual(result.stdout.strip(), '{"optional": [], "core": []}')

    def test_default_public_api_flow_avoids_optional_dependencies(self) -> None:
        result = self._run_python(
            """
            import json
            import os
            import sys
            import tempfile

            from coryl import Coryl

            with tempfile.TemporaryDirectory() as temp_dir:
                previous_cwd = os.getcwd()
                os.chdir(temp_dir)
                try:
                    app = Coryl(root=".")
                    settings = app.configs.add("settings", "config/settings.toml")
                    settings.save({"name": "default-flow"})
                    loaded = sorted(
                        set(sys.modules).intersection(
                            {
                                "yaml",
                                "pydantic",
                                "platformdirs",
                                "diskcache",
                                "watchfiles",
                                "fsspec",
                                "filelock",
                            }
                        )
                    )
                    print(json.dumps({"name": settings.load()["name"], "optional": loaded}))
                finally:
                    os.chdir(previous_cwd)
            """
        )
        self.assertEqual(
            result.stdout.strip(), '{"name": "default-flow", "optional": []}'
        )

    def test_readme_python_examples_run(self) -> None:
        readme = README_PATH.read_text(encoding="utf-8")
        python_blocks = re.findall(r"```python\r?\n(.*?)```", readme, flags=re.DOTALL)

        self.assertGreaterEqual(len(python_blocks), 1)
        for block in python_blocks:
            with tempfile.TemporaryDirectory() as temp_dir:
                self._run_python(
                    block,
                    cwd=temp_dir,
                )

    def test_examples_directory_contains_required_files(self) -> None:
        example_names = {path.name for path in (PROJECT_ROOT / "examples").glob("*.py")}
        self.assertTrue(
            {
                "simple_local_app.py",
                "cli_tool_config.py",
                "api_cache.py",
                "desktop_app_assets.py",
                "manifest_startup.py",
                "package_assets.py",
                "typed_config.py",
                "layered_config.py",
                "cache_diskcache.py",
                "fsspec_memory.py",
                "diagnostics_cli.py",
            }.issubset(example_names)
        )

    def test_examples_run(self) -> None:
        for example_name in (
            "simple_local_app.py",
            "cli_tool_config.py",
            "api_cache.py",
            "desktop_app_assets.py",
            "manifest_startup.py",
            "package_assets.py",
            "layered_config.py",
            "diagnostics_cli.py",
        ):
            self._run_example(example_name)

    def test_typed_config_example_runs_with_fake_pydantic(self) -> None:
        self._run_example(
            "typed_config.py",
            modules={"pydantic.py": FAKE_PYDANTIC_MODULE},
        )

    def _run_example(
        self,
        example_name: str,
        *,
        modules: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        script_path = PROJECT_ROOT / "examples" / example_name
        return self._run_python(
            script_path.read_text(encoding="utf-8"),
            modules=modules,
        )

    def _run_python(
        self,
        code: str,
        *,
        cwd: str | None = None,
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
                        textwrap.dedent(content).lstrip(),
                        encoding="utf-8",
                    )
                pythonpath_parts.insert(0, str(module_root))

            existing_pythonpath = os.environ.get("PYTHONPATH")
            if existing_pythonpath:
                pythonpath_parts.append(existing_pythonpath)

            env = os.environ.copy()
            env["PYTHONPATH"] = os.pathsep.join(pythonpath_parts)
            completed = subprocess.run(
                [sys.executable, "-c", textwrap.dedent(code)],
                capture_output=True,
                check=False,
                cwd=cwd or str(PROJECT_ROOT),
                env=env,
                text=True,
            )
            if completed.returncode != 0:
                self.fail(
                    "Subprocess failed.\n"
                    f"stdout:\n{completed.stdout}\n"
                    f"stderr:\n{completed.stderr}"
                )
            return completed
        finally:
            if temp_modules is not None:
                temp_modules.cleanup()


if __name__ == "__main__":
    unittest.main()
