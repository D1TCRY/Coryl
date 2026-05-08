from __future__ import annotations

import importlib.util
import shutil
from pathlib import Path

import pytest

from coryl import (
    ConfigResource,
    Coryl,
    CorylOptionalDependencyError,
    CorylValidationError,
    DiskCacheResource,
    ManifestFormatError,
)

FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures" / "manifests"
YAML_AVAILABLE = importlib.util.find_spec("yaml") is not None


def _copy_manifest_fixture(
    tmp_path: Path, fixture_name: str, *, target_name: str | None = None
) -> Path:
    source = FIXTURE_ROOT / fixture_name
    destination = tmp_path / (target_name or source.name)
    shutil.copyfile(source, destination)
    return destination


def _assert_loaded_v2_manifest(app: Coryl, tmp_path: Path) -> None:
    assert app.manifest is not None
    assert app.manifest["version"] == 2

    settings = app.configs.get("settings")
    assert isinstance(settings, ConfigResource)
    assert settings.readonly is True
    assert settings.required is True
    assert settings.declared_format == "toml"
    assert settings.schema == "app.settings.v1"
    assert settings.exists() is False

    notes = app.data.get("notes")
    assert notes.exists() is True
    assert notes.path == (tmp_path / "data" / "notes.txt").resolve()

    cache = app.caches.get("http_cache")
    assert isinstance(cache, DiskCacheResource)
    assert cache.backend == "diskcache"
    assert cache.exists() is False

    ui = app.assets.get("ui")
    assert ui.exists() is False


@pytest.mark.parametrize(
    ("fixture_name", "target_name"),
    [
        ("v2.json", "app.json"),
        ("v2.toml", "app.toml"),
        pytest.param(
            "v2.yaml",
            "app.yaml",
            marks=pytest.mark.skipif(
                not YAML_AVAILABLE, reason="PyYAML is not installed"
            ),
        ),
    ],
)
def test_v2_manifest_fixtures_load_via_constructor_and_load_manifest(
    tmp_path: Path,
    fixture_name: str,
    target_name: str,
) -> None:
    manifest_path = _copy_manifest_fixture(
        tmp_path, fixture_name, target_name=target_name
    )

    app = Coryl(root=tmp_path, manifest_path=manifest_path.name)

    assert app.manifest_path == manifest_path.resolve()
    _assert_loaded_v2_manifest(app, tmp_path)

    loaded_manager = Coryl(root=tmp_path)
    manifest = loaded_manager.load_manifest(Path(manifest_path.name))

    assert manifest["version"] == 2
    assert loaded_manager.manifest_path == manifest_path.resolve()
    _assert_loaded_v2_manifest(loaded_manager, tmp_path)


def test_legacy_manifest_fixture_preserves_compatibility(tmp_path: Path) -> None:
    manifest_path = _copy_manifest_fixture(
        tmp_path, "legacy.json", target_name="app.json"
    )

    app = Coryl(root=tmp_path, manifest_path=manifest_path.name)

    assert sorted(app.resources) == ["http_cache", "notes", "settings", "ui"]
    assert app.file("settings").role == "resource"
    assert app.file("notes").exists() is True
    assert app.directory("http_cache").role == "resource"
    assert app.directory("ui").exists() is True


def test_manifest_rejects_missing_path_field(tmp_path: Path) -> None:
    manifest_path = tmp_path / "app.toml"
    manifest_path.write_text(
        """
version = 2

[resources.settings]
kind = "file"
role = "config"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ManifestFormatError, match="path"):
        Coryl(root=tmp_path, manifest_path=manifest_path.name)


@pytest.mark.parametrize(
    ("resource_name", "path_value", "kind", "role", "message"),
    [
        (
            "settings",
            "config",
            "directory",
            "config",
            "Config resources must be files.",
        ),
        (
            "http_cache",
            ".cache/http.db",
            "file",
            "cache",
            "Cache and asset resources must be directories.",
        ),
        (
            "ui",
            "assets/logo.svg",
            "file",
            "assets",
            "Cache and asset resources must be directories.",
        ),
    ],
)
def test_manifest_rejects_invalid_role_kind_combinations(
    tmp_path: Path,
    resource_name: str,
    path_value: str,
    kind: str,
    role: str,
    message: str,
) -> None:
    manifest_path = tmp_path / "app.toml"
    manifest_path.write_text(
        (
            "version = 2\n\n"
            f"[resources.{resource_name}]\n"
            f'path = "{path_value}"\n'
            f'kind = "{kind}"\n'
            f'role = "{role}"\n'
        ),
        encoding="utf-8",
    )

    with pytest.raises(CorylValidationError, match=message):
        Coryl(root=tmp_path, manifest_path=manifest_path.name)


@pytest.mark.skipif(not YAML_AVAILABLE, reason="PyYAML is not installed")
def test_yaml_manifest_rejects_duplicate_resource_names(tmp_path: Path) -> None:
    manifest_path = tmp_path / "app.yaml"
    manifest_path.write_text(
        """
version: 2
resources:
  settings:
    path: config/settings.toml
    kind: file
  settings:
    path: config/other-settings.toml
    kind: file
""".strip()
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ManifestFormatError, match="Duplicate key 'settings'"):
        Coryl(root=tmp_path, manifest_path=manifest_path.name)


def test_audit_paths_includes_manifest_and_imperative_resources(tmp_path: Path) -> None:
    manifest_path = _copy_manifest_fixture(tmp_path, "v2.toml", target_name="app.toml")
    app = Coryl(root=tmp_path, manifest_path=manifest_path.name)
    app.register_file("report", "reports/daily.txt", create=False)
    app.register(
        "extra_cache",
        {
            "path": ".cache/extra",
            "kind": "directory",
            "role": "cache",
            "create": False,
            "backend": "diskcache",
        },
    )

    audit = app.audit_paths()

    assert audit["root"] == str(tmp_path.resolve())
    assert sorted(audit["resources"]) == [
        "extra_cache",
        "http_cache",
        "notes",
        "report",
        "settings",
        "ui",
    ]

    for details in audit["resources"].values():
        assert set(details) == {"exists", "kind", "path", "role", "safe"}
        assert details["safe"] is True

    assert audit["resources"]["notes"]["exists"] is True
    assert audit["resources"]["settings"]["exists"] is False
    assert audit["resources"]["ui"]["exists"] is False
    assert audit["resources"]["report"]["exists"] is False
    assert audit["resources"]["extra_cache"]["exists"] is False


def test_manifest_loaded_diskcache_backend_stays_lazy_until_used(
    tmp_path: Path,
) -> None:
    manifest_path = _copy_manifest_fixture(tmp_path, "v2.toml", target_name="app.toml")
    app = Coryl(root=tmp_path, manifest_path=manifest_path.name)
    cache = app.caches.get("http_cache")

    assert isinstance(cache, DiskCacheResource)
    assert app.audit_paths()["resources"]["http_cache"]["safe"] is True

    if importlib.util.find_spec("diskcache") is None:
        with pytest.raises(CorylOptionalDependencyError, match="coryl\\[diskcache\\]"):
            cache.clear()
        return

    cache.set("users:42", {"id": 42})
    assert cache.get("users:42") == {"id": 42}
    cache.clear()
    assert cache.get("users:42") is None
