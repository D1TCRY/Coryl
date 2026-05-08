from __future__ import annotations

import os
import subprocess
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

from coryl import Coryl, CorylPathError, CorylUnsafePathError, ResourceSpec


@pytest.fixture
def make_directory_link() -> Iterator[Callable[[Path, Path], None]]:
    created_links: list[Path] = []

    def _make_directory_link(link_path: Path, target_path: Path) -> None:
        link_path.parent.mkdir(parents=True, exist_ok=True)
        if os.name == "nt":
            result = subprocess.run(
                ["cmd", "/c", "mklink", "/J", str(link_path), str(target_path)],
                capture_output=True,
                check=False,
                text=True,
            )
            if result.returncode != 0:
                pytest.skip(result.stderr.strip() or result.stdout.strip())
        else:
            try:
                link_path.symlink_to(target_path, target_is_directory=True)
            except OSError as error:
                pytest.skip(f"Directory symlinks are unavailable: {error}")
        created_links.append(link_path)

    yield _make_directory_link

    for link_path in reversed(created_links):
        if not link_path.exists() and not link_path.is_symlink():
            continue
        if os.name == "nt":
            subprocess.run(
                ["cmd", "/c", "rmdir", str(link_path)],
                capture_output=True,
                check=False,
                text=True,
            )
        else:
            link_path.unlink()


@pytest.mark.parametrize(
    ("method_name", "relative_path"),
    [
        ("register_file", "safe/file.txt"),
        ("register_directory", "safe/folder"),
        ("register_config", "config/settings.json"),
        ("register_cache", ".cache/http"),
        ("register_assets", "assets/ui"),
        ("register_data", "data/state.json"),
        ("register_log", "logs/app.log"),
    ],
)
def test_relative_paths_inside_root_are_accepted(
    tmp_path: Path,
    method_name: str,
    relative_path: str,
) -> None:
    app = Coryl(root=tmp_path)

    resource = getattr(app, method_name)("sample", relative_path)

    assert resource.path.is_relative_to(tmp_path.resolve())


@pytest.mark.parametrize(
    ("method_name", "suffix"),
    [
        ("register_file", "data/absolute.txt"),
        ("register_directory", "data/absolute"),
        ("register_config", "config/settings.json"),
        ("register_cache", ".cache/http"),
        ("register_assets", "assets/ui"),
        ("register_data", "data/state.json"),
        ("register_log", "logs/app.log"),
    ],
)
def test_absolute_paths_are_rejected_by_default(
    tmp_path: Path,
    method_name: str,
    suffix: str,
) -> None:
    app = Coryl(root=tmp_path)
    absolute_path = tmp_path / suffix

    with pytest.raises(CorylPathError):
        getattr(app, method_name)("sample", absolute_path)


@pytest.mark.parametrize(
    ("method_name", "relative_path"),
    [
        ("register_file", "../escape.txt"),
        ("register_directory", "safe/../escape"),
        ("register_config", "config/../settings.json"),
        ("register_cache", ".cache/../http"),
        ("register_assets", "assets/../ui"),
        ("register_data", "data/../state.json"),
        ("register_log", "logs/../app.log"),
    ],
)
def test_parent_traversal_is_rejected(
    tmp_path: Path,
    method_name: str,
    relative_path: str,
) -> None:
    app = Coryl(root=tmp_path)

    with pytest.raises(CorylUnsafePathError):
        getattr(app, method_name)("sample", relative_path)


@pytest.mark.parametrize(
    "relative_path",
    [
        "safe/../file.txt",
        "safe/nested/../../file.txt",
        "config/inner/../../settings.json",
    ],
)
def test_normalizing_back_inside_root_is_still_rejected(
    tmp_path: Path,
    relative_path: str,
) -> None:
    app = Coryl(root=tmp_path)

    with pytest.raises(CorylUnsafePathError):
        app.register_file("sample", relative_path)


def test_child_paths_from_directory_resources_cannot_escape_parent(
    tmp_path: Path,
) -> None:
    app = Coryl(root=tmp_path)
    assets = app.register_assets("assets", "assets")

    with pytest.raises(CorylUnsafePathError):
        assets.file("images", "..", "escape.txt")

    with pytest.raises(CorylUnsafePathError):
        assets.directory("nested", "..", "..", "escape")


def test_child_paths_reject_absolute_paths(tmp_path: Path) -> None:
    app = Coryl(root=tmp_path)
    assets = app.register_assets("assets", "assets")

    with pytest.raises(CorylPathError):
        assets.file(tmp_path / "assets" / "logo.svg")


def test_resource_specs_reject_unsafe_paths_before_registration(tmp_path: Path) -> None:
    del tmp_path

    with pytest.raises(CorylPathError):
        ResourceSpec.file(Path.cwd() / "absolute.txt")

    with pytest.raises(CorylUnsafePathError):
        ResourceSpec.directory("safe/../escape")


def test_symlinked_directory_registration_cannot_escape_root(
    tmp_path: Path,
    tmp_path_factory: pytest.TempPathFactory,
    make_directory_link: Callable[[Path, Path], None],
) -> None:
    outside_root = tmp_path_factory.mktemp("coryl-outside-registration")
    make_directory_link(tmp_path / "linked-assets", outside_root)
    app = Coryl(root=tmp_path)

    with pytest.raises(CorylUnsafePathError):
        app.register_directory("linked", "linked-assets")


def test_symlinked_child_paths_cannot_escape_directory_resource(
    tmp_path: Path,
    tmp_path_factory: pytest.TempPathFactory,
    make_directory_link: Callable[[Path, Path], None],
) -> None:
    outside_root = tmp_path_factory.mktemp("coryl-outside-child")
    make_directory_link(tmp_path / "assets" / "linked", outside_root)
    app = Coryl(root=tmp_path)
    assets = app.register_assets("assets", "assets")

    with pytest.raises(CorylUnsafePathError):
        assets.file("linked", "secret.txt")
