from __future__ import annotations

from unittest import mock

import pytest

from coryl import Coryl, CorylOptionalDependencyError


@pytest.mark.parametrize(
    "register",
    [
        lambda app: app.caches.diskcache("api", ".cache/api"),
        lambda app: app.caches.add("api", ".cache/api", backend="diskcache"),
    ],
)
def test_diskcache_missing_dependency_error_is_clear(
    tmp_path,
    register,
) -> None:
    app = Coryl(root=tmp_path)

    with mock.patch(
        "coryl.resources.import_module",
        side_effect=ModuleNotFoundError("No module named 'diskcache'"),
    ):
        with pytest.raises(
            CorylOptionalDependencyError,
            match=r"Install coryl\[diskcache\] to use the diskcache backend\.",
        ):
            register(app)
