"""Custom exceptions for Coryl."""


class CorylError(Exception):
    """Base exception for the package."""


class ResourceNotRegisteredError(CorylError, KeyError):
    """Raised when a resource name is unknown."""


class ResourceKindError(CorylError, TypeError):
    """Raised when a resource is used as the wrong kind."""


class UnsafePathError(CorylError, ValueError):
    """Raised when a resource path escapes the configured root."""


class ResourceConflictError(CorylError, ValueError):
    """Raised when registering a resource name twice without replacement."""


class ManifestFormatError(CorylError, ValueError):
    """Raised when a manifest file cannot be interpreted."""

