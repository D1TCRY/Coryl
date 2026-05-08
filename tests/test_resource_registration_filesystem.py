from __future__ import annotations

from pathlib import Path

import pytest

from coryl import AssetGroup, CacheResource, ConfigResource, Coryl, Resource, ResourceSpec


@pytest.mark.parametrize(
    ("method_name", "relative_path", "expected_type", "expected_kind", "expected_role"),
    [
        ("register_file", "files/report.txt", Resource, "file", "resource"),
        ("register_directory", "folders/exports", Resource, "directory", "resource"),
        ("register_config", "config/settings.toml", ConfigResource, "file", "config"),
        ("register_cache", ".cache/http", CacheResource, "directory", "cache"),
        ("register_assets", "assets/ui", AssetGroup, "directory", "assets"),
    ],
)
def test_registration_helpers_return_expected_resource_shapes(
    tmp_path: Path,
    method_name: str,
    relative_path: str,
    expected_type: type[object],
    expected_kind: str,
    expected_role: str,
) -> None:
    app = Coryl(root=tmp_path)

    resource = getattr(app, method_name)("sample", relative_path)

    assert isinstance(resource, expected_type)
    assert resource.kind == expected_kind
    assert resource.role == expected_role
    assert app.resource("sample") is resource


@pytest.mark.parametrize(
    ("method_name", "relative_path", "expected_kind", "expected_role"),
    [
        ("register_data", "data/state.json", "file", "data"),
        ("register_data", "data/snapshots", "directory", "data"),
        ("register_log", "logs/app.log", "file", "logs"),
        ("register_log", "logs/archive", "directory", "logs"),
    ],
)
def test_data_and_log_registration_infer_kind_from_path(
    tmp_path: Path,
    method_name: str,
    relative_path: str,
    expected_kind: str,
    expected_role: str,
) -> None:
    app = Coryl(root=tmp_path)

    resource = getattr(app, method_name)("sample", relative_path)

    assert resource.kind == expected_kind
    assert resource.role == expected_role
    assert resource.path.is_relative_to(tmp_path.resolve())


@pytest.mark.parametrize(
    ("factory", "relative_path", "expected_kind", "expected_role"),
    [
        (ResourceSpec.file, "runtime/report.txt", "file", "resource"),
        (ResourceSpec.directory, "runtime/exports", "directory", "resource"),
        (ResourceSpec.config, "config/settings.json", "file", "config"),
        (ResourceSpec.cache, ".cache/http", "directory", "cache"),
        (ResourceSpec.assets, "assets/ui", "directory", "assets"),
    ],
)
def test_resource_spec_factories_preserve_expected_metadata(
    factory: object,
    relative_path: str,
    expected_kind: str,
    expected_role: str,
) -> None:
    spec = factory(relative_path)

    assert isinstance(spec, ResourceSpec)
    assert spec.relative_path == Path(relative_path)
    assert spec.kind == expected_kind
    assert spec.role == expected_role
