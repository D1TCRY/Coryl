"""Coryl public package API."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

_EXCEPTION_EXPORTS = {
    "CorylError": "exceptions",
    "CorylInvalidResourceKindError": "exceptions",
    "CorylLockTimeoutError": "exceptions",
    "CorylOptionalDependencyError": "exceptions",
    "CorylPathError": "exceptions",
    "CorylReadOnlyResourceError": "exceptions",
    "CorylResourceNotFoundError": "exceptions",
    "CorylUnsafePathError": "exceptions",
    "CorylUnsupportedFormatError": "exceptions",
    "CorylValidationError": "exceptions",
    "ManifestFormatError": "exceptions",
    "ReadOnlyResourceError": "exceptions",
    "ResourceConflictError": "exceptions",
    "ResourceKindError": "exceptions",
    "ResourceNotRegisteredError": "exceptions",
    "UnsupportedFormatError": "exceptions",
    "UnsafePathError": "exceptions",
}
_MANAGER_EXPORTS = {
    "MANIFEST_VERSION": "manager",
    "AssetNamespace": "manager",
    "CacheNamespace": "manager",
    "ConfigNamespace": "manager",
    "Coryl": "manager",
    "DataNamespace": "manager",
    "LogNamespace": "manager",
    "ResourceManager": "manager",
}
_RESOURCE_EXPORTS = {
    "AssetGroup": "resources",
    "CacheResource": "resources",
    "ConfigResource": "resources",
    "DiskCacheResource": "resources",
    "LayeredConfigResource": "resources",
    "PackageAssetGroup": "resources",
    "PackageAssetResource": "resources",
    "Resource": "resources",
    "ResourceKind": "resources",
    "ResourceRole": "resources",
    "ResourceSpec": "resources",
}
_EXPORTS = {
    **_EXCEPTION_EXPORTS,
    **_MANAGER_EXPORTS,
    **_RESOURCE_EXPORTS,
}

__all__ = [
    "AssetGroup",
    "CacheResource",
    "ConfigResource",
    "Coryl",
    "CorylError",
    "CorylInvalidResourceKindError",
    "CorylLockTimeoutError",
    "CorylOptionalDependencyError",
    "CorylPathError",
    "CorylReadOnlyResourceError",
    "CorylResourceNotFoundError",
    "CorylUnsafePathError",
    "CorylUnsupportedFormatError",
    "CorylValidationError",
    "LayeredConfigResource",
    "MANIFEST_VERSION",
    "ManifestFormatError",
    "Resource",
    "ResourceConflictError",
    "ResourceKindError",
    "ResourceManager",
    "ResourceNotRegisteredError",
    "ResourceSpec",
    "UnsupportedFormatError",
]


def __getattr__(name: str) -> Any:
    module_name = _EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    module = import_module(f".{module_name}", __name__)
    value = getattr(module, name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(_EXPORTS))


if TYPE_CHECKING:
    from .exceptions import (
        CorylError,
        CorylInvalidResourceKindError,
        CorylLockTimeoutError,
        CorylOptionalDependencyError,
        CorylPathError,
        CorylReadOnlyResourceError,
        CorylResourceNotFoundError,
        CorylUnsafePathError,
        CorylUnsupportedFormatError,
        CorylValidationError,
        ManifestFormatError,
        ReadOnlyResourceError,
        ResourceConflictError,
        ResourceKindError,
        ResourceNotRegisteredError,
        UnsupportedFormatError,
        UnsafePathError,
    )
    from .manager import (
        MANIFEST_VERSION,
        AssetNamespace,
        CacheNamespace,
        ConfigNamespace,
        Coryl,
        DataNamespace,
        LogNamespace,
        ResourceManager,
    )
    from .resources import (
        AssetGroup,
        CacheResource,
        ConfigResource,
        DiskCacheResource,
        LayeredConfigResource,
        PackageAssetGroup,
        PackageAssetResource,
        Resource,
        ResourceKind,
        ResourceRole,
        ResourceSpec,
    )
