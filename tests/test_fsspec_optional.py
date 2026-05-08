from __future__ import annotations

from unittest import mock

import pytest

from coryl import Coryl, CorylOptionalDependencyError


def _construct_with_fs() -> Coryl:
    return Coryl.with_fs(root="memory://app", protocol="memory")


def _construct_with_filesystem_arg() -> Coryl:
    return Coryl(root="memory://app", filesystem="fsspec", protocol="memory")


@pytest.mark.parametrize(
    "constructor",
    [_construct_with_fs, _construct_with_filesystem_arg],
    ids=["with-fs", "filesystem-arg"],
)
def test_missing_fsspec_dependency_error_is_clear(constructor: object) -> None:
    message = (
        "Optional fsspec filesystem support requires the 'fsspec' dependency. "
        "Install it with 'pip install coryl[fsspec]'."
    )

    with mock.patch(
        "coryl._fs.import_module",
        side_effect=ModuleNotFoundError("No module named 'fsspec'"),
    ):
        with pytest.raises(CorylOptionalDependencyError, match="pip install coryl\\[fsspec\\]") as caught:
            constructor()

    assert str(caught.value) == message
