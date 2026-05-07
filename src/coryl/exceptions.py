"""Custom exceptions for Coryl."""


class CorylError(Exception):
    """Base exception for the package."""


class CorylValidationError(CorylError, ValueError):
    """Raised when Coryl receives invalid configuration or resource metadata."""


class CorylPathError(CorylValidationError):
    """Raised when a managed path is malformed for Coryl's safety model."""


class CorylUnsafePathError(CorylPathError):
    """Raised when a managed path would escape its allowed root."""


class CorylResourceNotFoundError(CorylError, KeyError):
    """Raised when a resource name is unknown."""


class CorylInvalidResourceKindError(CorylError, TypeError):
    """Raised when a resource kind is invalid or used incorrectly."""


class CorylUnsupportedFormatError(CorylValidationError):
    """Raised when a file format is unsupported for a requested operation."""


class CorylOptionalDependencyError(CorylError, ImportError):
    """Raised when an optional dependency is required for a requested feature."""


class CorylLockTimeoutError(CorylError, TimeoutError):
    """Raised when a lock cannot be acquired before the configured timeout."""


class CorylReadOnlyResourceError(CorylError, PermissionError):
    """Raised when a mutation is attempted on a read-only resource."""


class ResourceConflictError(CorylValidationError):
    """Raised when registering a resource name twice without replacement."""


class ManifestFormatError(CorylValidationError):
    """Raised when a manifest file cannot be interpreted."""


ResourceNotRegisteredError = CorylResourceNotFoundError
ResourceKindError = CorylInvalidResourceKindError
UnsafePathError = CorylUnsafePathError
UnsupportedFormatError = CorylUnsupportedFormatError
ReadOnlyResourceError = CorylReadOnlyResourceError
